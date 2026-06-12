import asyncio
import json
import re
import time
from typing import Any

try:
    from groq import AsyncGroq
except ImportError:  # pragma: no cover - exercised when optional SDK is absent
    AsyncGroq = None

from .config import Settings
from .models import RawThreat, TriageResult
from .observability import LangfuseTracer


TRIAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "record_threat_triage",
        "description": "Return the final cybersecurity triage decision for one threat intelligence item.",
        "parameters": {
            "type": "object",
            "properties": {
                "severity": {"type": "integer", "minimum": 1, "maximum": 10},
                "threat_type": {"type": "string"},
                "summary": {"type": "string", "description": "Exactly two concise executive sentences."},
                "decision": {"type": "string", "enum": ["IGNORE", "MONITOR", "ALERT"]},
                "reasoning": {"type": "string"},
            },
            "required": ["severity", "threat_type", "summary", "decision", "reasoning"],
        },
    },
}


class ThreatTriageAI:
    def __init__(self, settings: Settings, tracer: LangfuseTracer):
        self.settings = settings
        self.tracer = tracer
        self.client = AsyncGroq(api_key=settings.groq_api_key) if AsyncGroq and settings.groq_api_key else None

    async def triage(self, threat: RawThreat) -> TriageResult:
        trace_id = self.tracer.trace_id()
        start = time.perf_counter()
        raw_hint = json.dumps(threat.raw_data, default=str)[:6000]
        prompt = (
            "You are ThreatLens, an autonomous cyber threat intelligence analyst. "
            "Score the item from 1-10, classify it, write exactly two executive-summary sentences, "
            "and choose IGNORE, MONITOR, or ALERT. Favor ALERT for exploitable internet-facing RCE, credential exposure, "
            "known exploitation, or exposed management services.\n\n"
            f"Source: {threat.source}\nTarget: {threat.target}\nObserved at: {threat.timestamp.isoformat()}\nRaw intel:\n{raw_hint}"
        )
        trace = self.tracer.create_trace(
            trace_id,
            "threat-triage",
            {"source": threat.source, "target": threat.target, "raw_event_id": threat.id},
            ["threat-triage", f"source:{threat.source}"],
        )
        if self.client:
            try:
                backoff_delays = [0.5, 1.0, 2.0]
                response = None
                for attempt in range(3):
                    try:
                        response = await self.client.chat.completions.create(
                            model=self.settings.groq_model,
                            max_tokens=700,
                            temperature=0.1,
                            tools=[TRIAGE_TOOL],
                            tool_choice={"type": "function", "function": {"name": "record_threat_triage"}},
                            messages=[{"role": "user", "content": prompt}],
                        )
                        break
                    except Exception as retry_exc:
                        exc_name = type(retry_exc).__name__
                        if exc_name in ("AuthenticationError", "PermissionDeniedError"):
                            raise
                        if attempt < 2 and exc_name in (
                            "RateLimitError", "APITimeoutError", "APIConnectionError",
                            "Timeout", "ConnectError", "ReadTimeout",
                        ):
                            await asyncio.sleep(backoff_delays[attempt])
                            continue
                        raise
                payload = self._extract_tool(response)
                latency_ms = int((time.perf_counter() - start) * 1000)
                result = self._result_from_payload(payload, latency_ms, trace_id)
                usage = getattr(response, "usage", None)
                prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                result.prompt_tokens = prompt_tokens
                result.completion_tokens = completion_tokens
                self._log_trace(trace, prompt, payload, result, prompt_tokens, completion_tokens)
                return result
            except Exception as exc:
                fallback = self.local_triage(threat, trace_id, int((time.perf_counter() - start) * 1000))
                fallback.reasoning = f"{fallback.reasoning} Groq API fallback: {type(exc).__name__}."
                self._log_trace(trace, prompt, fallback.model_dump(), fallback, 0, 0)
                return fallback

        result = self.local_triage(threat, trace_id, int((time.perf_counter() - start) * 1000))
        self._log_trace(trace, prompt, result.model_dump(), result, 0, 0)
        return result

    async def incident_report(self, alert_events: list[dict[str, Any]]) -> tuple[str, str]:
        trace_id = self.tracer.trace_id()
        trace = self.tracer.create_trace(trace_id, "incident-report", {"alerts": len(alert_events)}, ["incident-report"])
        prompt = (
            "Write a concise incident report for these ALERT-level cyber threat events. "
            "Include executive impact, likely attack path, immediate containment, and next 24-hour actions.\n"
            f"{json.dumps(alert_events, default=str)[:12000]}"
        )
        start = time.perf_counter()
        if self.client:
            try:
                response = await self.client.chat.completions.create(
                    model=self.settings.groq_model,
                    max_tokens=1200,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.choices[0].message.content or self._local_incident_report()
                usage = getattr(response, "usage", None)
                self.tracer.generation(
                    trace,
                    "incident-report",
                    self.settings.groq_model,
                    prompt,
                    text,
                    {
                        "input": int(getattr(usage, "prompt_tokens", 0) or 0),
                        "output": int(getattr(usage, "completion_tokens", 0) or 0),
                    },
                    {"generation_type": "incident-report"},
                    int((time.perf_counter() - start) * 1000),
                )
                return text, trace_id
            except Exception:
                report = self._local_incident_report()
                self.tracer.generation(trace, "incident-report", self.settings.groq_model, prompt, report, {}, {}, 0)
                return report, trace_id
        report = "ThreatLens incident report: ALERT-level activity was detected across the monitored attack surface. Prioritize exposed remote services, patch critical CVEs, rotate affected credentials, and verify compensating controls within 24 hours."
        self.tracer.generation(trace, "incident-report", self.settings.groq_model, prompt, report, {}, {}, 0)
        return report, trace_id

    @staticmethod
    def _local_incident_report() -> str:
        return "ThreatLens incident report: ALERT-level activity was detected across the monitored attack surface. Prioritize exposed remote services, patch critical CVEs, rotate affected credentials, and verify compensating controls within 24 hours."

    def local_triage(self, threat: RawThreat, trace_id: str, latency_ms: int) -> TriageResult:
        raw = threat.raw_data
        text = json.dumps(raw, default=str).lower()
        severity = 3
        threat_type = "threat intelligence"
        if threat.source == "nvd" or "cve-" in text:
            threat_type = "CVE"
            severity = max(severity, int(round(float(raw.get("cvss_score") or 0))) or 5)
        if threat.source == "github":
            threat_type = "supply chain advisory"
            severity = max(severity, {"critical": 9, "high": 8, "medium": 5, "low": 3}.get(str(raw.get("severity", "")).lower(), 6))
        if threat.source == "shodan":
            threat_type = "exposed service"
            ports = set(raw.get("ports") or [])
            severity = max(severity, 8 if ports.intersection({3389, 9200, 5985, 6379, 27017}) else 5)
            if raw.get("vulns"):
                severity = max(severity, 9)
        if threat.source == "hibp":
            threat_type = "breach"
            severity = max(severity, 7 if raw.get("breach_count", 0) >= 2 else 5)
        if re.search(r"rce|remote code|command execution|credential|password|token|exploited", text):
            severity = max(severity, 8)
        decision = "ALERT" if severity >= 8 else "MONITOR" if severity >= 5 else "IGNORE"
        summary = (
            f"{threat.target} has a {threat_type.lower()} signal from {threat.source} scored {severity}/10. "
            f"ThreatLens recommends {decision.lower()} handling based on exposure, exploitability, and business impact indicators."
        )
        return TriageResult(
            severity=min(10, max(1, severity)),
            threat_type=threat_type,
            summary=summary,
            decision=decision,
            reasoning="Deterministic demo triage used weighted indicators for exploitability, exposure, sensitive data, and source severity.",
            latency_ms=max(latency_ms, 1),
            trace_id=trace_id,
        )

    def _log_trace(
        self,
        trace: Any,
        prompt: str,
        output: Any,
        result: TriageResult,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        bucket = "critical" if result.severity >= 9 else "high" if result.severity >= 7 else "med" if result.severity >= 4 else "low"
        metadata = {
            "severity": result.severity,
            "decision": result.decision,
            "threat_type": result.threat_type,
            "severity_bucket": bucket,
            "generation_type": "threat-triage",
        }
        self.tracer.generation(
            trace,
            "threat-triage",
            self.settings.groq_model,
            prompt,
            output,
            {"input": prompt_tokens, "output": completion_tokens, "total": prompt_tokens + completion_tokens},
            metadata,
            result.latency_ms,
        )
        self.tracer.score(trace, "severity_score", result.severity / 10, result.reasoning)
        self.tracer.score(trace, "alert_decision", 1 if result.decision == "ALERT" else 0, result.decision)

    @staticmethod
    def _extract_tool(response: Any) -> dict[str, Any]:
        tool_calls = response.choices[0].message.tool_calls or []
        for call in tool_calls:
            function = getattr(call, "function", None)
            if getattr(function, "name", "") == "record_threat_triage":
                return json.loads(function.arguments or "{}")
        raise ValueError("Groq did not return record_threat_triage tool output")

    @staticmethod
    def _result_from_payload(payload: dict[str, Any], latency_ms: int, trace_id: str) -> TriageResult:
        return TriageResult(
            severity=int(payload["severity"]),
            threat_type=str(payload["threat_type"]),
            summary=str(payload["summary"]),
            decision=payload["decision"],
            reasoning=str(payload["reasoning"]),
            latency_ms=max(latency_ms, 1),
            trace_id=trace_id,
        )
