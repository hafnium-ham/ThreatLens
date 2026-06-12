import asyncio
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable

from .ai import ThreatTriageAI
from .collectors import ThreatCollectors
from .database import ClickHouse
from .models import AgentRun, CveIntel, ThreatEvent
from .observability import LangfuseTracer


Broadcast = Callable[[ThreatEvent], Awaitable[None]]


class ThreatLensAgent:
    def __init__(
        self,
        db: ClickHouse,
        collectors: ThreatCollectors,
        ai: ThreatTriageAI,
        tracer: LangfuseTracer,
        model: str,
        broadcast: Broadcast | None = None,
    ):
        self.db = db
        self.collectors = collectors
        self.ai = ai
        self.tracer = tracer
        self.model = model
        self.broadcast = broadcast
        self._lock = asyncio.Lock()

    async def run_once(self) -> AgentRun:
        async with self._lock:
            started = datetime.now(timezone.utc)
            run_trace_id = self.tracer.trace_id()
            trace = self.tracer.create_trace(run_trace_id, "agent-run", {"phase": "collect-triage-store-alert"}, ["agent-run"])
            raw_threats = await self.collectors.collect_all()
            events: list[ThreatEvent] = []
            for raw in raw_threats:
                triage = await self.ai.triage(raw)
                event = ThreatEvent(
                    id=f"{raw.id}-{uuid.uuid4().hex[:8]}",
                    timestamp=raw.timestamp,
                    source=raw.source,
                    threat_type=triage.threat_type,
                    target=raw.target,
                    severity=triage.severity,
                    raw_data={**raw.raw_data, "triage_reasoning": triage.reasoning},
                    ai_summary=triage.summary,
                    status=triage.decision,
                    triage_latency_ms=triage.latency_ms,
                    langfuse_trace_id=triage.trace_id,
                )
                events.append(event)
            alert_events = [event.model_dump(mode="json") for event in events if event.status == "ALERT"]
            if alert_events:
                report, incident_trace_id = await self.ai.incident_report(alert_events)
                for event in events:
                    if event.status == "ALERT":
                        event.raw_data["incident_report"] = report
                        event.raw_data["incident_trace_id"] = incident_trace_id
            self.db.insert_threats(events)
            self.db.upsert_cves(self._cves_from_events(events))
            duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            run = AgentRun(
                id=uuid.uuid4().hex,
                timestamp=started,
                duration_ms=duration_ms,
                threats_found=len(events),
                model_used=self.model,
                langfuse_trace_id=run_trace_id,
                status="success",
                severity_breakdown=self._severity_breakdown(events),
            )
            self.db.insert_agent_run(run)
            if trace:
                self.tracer.score(trace, "threats_found", len(events), "Threat events collected and stored")
                self.tracer.score(trace, "alert_count", len(alert_events), "ALERT-level threats detected")
            self.tracer.flush()
            if self.broadcast:
                for event in events:
                    await self.broadcast(event)
            return run

    def _cves_from_events(self, events: list[ThreatEvent]) -> list[CveIntel]:
        cves: list[CveIntel] = []
        for event in events:
            raw = event.raw_data
            cve_id = raw.get("cve_id") or (event.target if event.target.startswith("CVE-") else None)
            if not cve_id:
                continue
            products = raw.get("affected_products") or []
            if isinstance(products, str):
                products = [products]
            cves.append(
                CveIntel(
                    cve_id=cve_id,
                    published_date=event.timestamp,
                    cvss_score=float(raw.get("cvss_score") or event.severity),
                    description=raw.get("description") or raw.get("summary") or event.ai_summary,
                    affected_products=products[:20],
                    ai_triage_notes=f"{event.ai_summary} Decision: {event.status}; severity {event.severity}/10.",
                )
            )
        return cves

    @staticmethod
    def _severity_breakdown(events: list[ThreatEvent]) -> dict[str, int]:
        buckets = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for event in events:
            if event.severity >= 9:
                buckets["critical"] += 1
            elif event.severity >= 7:
                buckets["high"] += 1
            elif event.severity >= 5:
                buckets["medium"] += 1
            else:
                buckets["low"] += 1
        return buckets
