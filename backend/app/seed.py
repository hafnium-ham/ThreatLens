import random
import uuid
from datetime import datetime, timedelta, timezone

from .database import ClickHouse
from .models import AgentRun, CveIntel, ThreatEvent


SOURCES = ["nvd", "shodan", "github", "hibp"]
TARGETS = {
    "nvd": ["CVE-2026-34891", "CVE-2026-31207", "CVE-2026-28744", "CVE-2026-40112"],
    "shodan": ["203.0.113.10", "198.51.100.24", "192.0.2.45", "203.0.113.88"],
    "github": ["GHSA-demo-9x2p-rce7", "GHSA-demo-4m8q-token", "GHSA-demo-vault-ci"],
    "hibp": ["acme-corp.test", "contoso.test", "example.com"],
}


def seed_demo_data(db: ClickHouse) -> None:
    if db.threat_count() >= 50:
        return
    now = datetime.now(timezone.utc)
    events: list[ThreatEvent] = []
    random.seed(42)
    severities = (
        [random.choice([9, 10]) for _ in range(30)]
        + [random.choice([7, 8]) for _ in range(60)]
        + [random.choice([5, 6]) for _ in range(120)]
        + [random.choice([1, 2, 3, 4]) for _ in range(90)]
    )
    random.shuffle(severities)
    for idx, severity in enumerate(severities):
        source = random.choices(SOURCES, weights=[32, 28, 24, 16])[0]
        target = random.choice(TARGETS[source])
        threat_type = {
            "nvd": "CVE",
            "shodan": "exposed service",
            "github": "supply chain advisory",
            "hibp": "breach",
        }[source]
        decision = "ALERT" if severity >= 8 else "MONITOR" if severity >= 5 else "IGNORE"
        timestamp = now - timedelta(minutes=random.randint(0, 60 * 72))
        port = random.choice([22, 80, 443, 3389, 5985, 6379, 9200]) if source == "shodan" else None
        events.append(
            ThreatEvent(
                id=f"seed-{idx}-{uuid.uuid4().hex[:8]}",
                timestamp=timestamp,
                source=source,
                threat_type=threat_type,
                target=target,
                severity=severity,
                raw_data={
                    "demo": True,
                    "indicator": f"{source}:{target}",
                    "confidence": random.randint(62, 98),
                    "business_unit": random.choice(["payments", "identity", "platform", "data"]),
                    "ports": [port] if port else [],
                    "affected_products": random.sample(["Apache Struts", "OpenSSL", "Kubernetes", "Redis", "GitHub Actions", "Okta"], k=2),
                },
                ai_summary=(
                    f"{target} is producing a {threat_type.lower()} signal from {source.upper()} with severity {severity}/10. "
                    f"ThreatLens recommends {decision.lower()} handling after correlating exploitability, exposure, credential impact, and business-unit ownership."
                ),
                status=decision,
                triage_latency_ms=random.randint(260, 1800),
                langfuse_trace_id=uuid.uuid4().hex,
            )
        )
    db.insert_threats(events)
    cves = [
        CveIntel(
            cve_id="CVE-2026-34891",
            published_date=now - timedelta(hours=4),
            cvss_score=9.8,
            description="Unauthenticated remote code execution in Apache Struts file upload validation.",
            affected_products=["Apache Struts", "Java web applications"],
            ai_triage_notes="Internet-facing Struts applications should patch immediately and review WAF bypass telemetry.",
        ),
        CveIntel(
            cve_id="CVE-2026-31207",
            published_date=now - timedelta(hours=9),
            cvss_score=7.4,
            description="Privilege escalation in OpenSSL provider loading on misconfigured Linux hosts.",
            affected_products=["OpenSSL", "Linux servers"],
            ai_triage_notes="Monitor until affected hosts are inventoried; prioritize shared build and signing infrastructure.",
        ),
        CveIntel(
            cve_id="CVE-2026-28744",
            published_date=now - timedelta(hours=15),
            cvss_score=6.5,
            description="Cross-site scripting in Kubernetes dashboard extension may expose service account tokens.",
            affected_products=["Kubernetes dashboard", "Cluster extensions"],
            ai_triage_notes="Restrict dashboard access and rotate tokens for clusters with the extension enabled.",
        ),
    ]
    db.upsert_cves(cves)
    runs = [
        AgentRun(
            id=uuid.uuid4().hex,
            timestamp=now - timedelta(minutes=idx * 5),
            duration_ms=random.randint(2100, 7600),
            threats_found=random.randint(4, 14),
            model_used="llama-3.3-70b-versatile",
            langfuse_trace_id=uuid.uuid4().hex,
            status="success",
            severity_breakdown={"critical": random.randint(0, 2), "high": random.randint(0, 3), "medium": random.randint(1, 6), "low": random.randint(0, 4)},
        )
        for idx in range(15)
    ]
    for run in runs:
        db.insert_agent_run(run)
