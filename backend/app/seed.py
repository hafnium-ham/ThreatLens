import random
import uuid
from datetime import datetime, timedelta, timezone

from .database import ClickHouse
from .models import AgentRun, CveIntel, ThreatEvent


SOURCES = ["nvd", "shodan", "github", "hibp"]
TARGETS = {
    "nvd": [
        "CVE-2024-21762", "CVE-2024-3400", "CVE-2024-23897", "CVE-2024-27198",
        "CVE-2024-20353", "CVE-2024-4577", "CVE-2024-38077", "CVE-2024-6387",
    ],
    "shodan": [
        "203.0.113.10", "198.51.100.24", "192.0.2.45", "203.0.113.88",
        "10.42.0.7", "172.16.5.100", "198.51.100.50", "192.0.2.99",
    ],
    "github": [
        "GHSA-xvch-5gv4-984h", "GHSA-jfmj-5v4g-7637", "GHSA-2m39-62f4-q4rh",
        "GHSA-9cwg-mhxf-hh59", "GHSA-r7hg-2cpp-8wcv",
    ],
    "hibp": [
        "acme-corp.test", "contoso.test", "example.com", "globotech.test",
        "megafinance.test", "healthnet.test",
    ],
}

PRODUCTS = {
    "nvd": [
        ("Fortinet FortiOS", "SSL VPN appliance"),
        ("Palo Alto PAN-OS", "GlobalProtect firewall"),
        ("Jenkins CI", "automation server"),
        ("JetBrains TeamCity", "CI/CD platform"),
        ("Cisco ASA", "adaptive security appliance"),
        ("PHP CGI", "web scripting runtime"),
        ("Windows RRAS", "remote access service"),
        ("OpenSSH", "secure shell server"),
    ],
    "shodan": [
        ("Elasticsearch 7.x", "search cluster"),
        ("Redis 6.x", "in-memory data store"),
        ("Kubernetes API", "container orchestrator"),
        ("MongoDB 5.x", "document database"),
        ("RDP Gateway", "remote desktop"),
        ("Jenkins CI", "build server"),
        ("Grafana OSS", "observability dashboard"),
        ("MinIO S3", "object storage"),
    ],
    "github": [
        ("lodash", "npm utility library"),
        ("requests", "Python HTTP library"),
        ("axios", "JavaScript HTTP client"),
        ("spring-boot", "Java framework"),
        ("django", "Python web framework"),
    ],
    "hibp": [
        ("Corporate SSO", "identity provider"),
        ("Customer CRM", "relationship management"),
        ("Vendor Portal", "supplier management"),
        ("HR System", "employee management"),
        ("Payment Gateway", "financial processing"),
        ("Health Records", "medical data system"),
    ],
}

SUMMARIES = {
    "nvd": [
        "{target} is an actively exploited {product} vulnerability allowing unauthenticated remote code execution via crafted requests. "
        "Immediate patching of {desc} instances is critical to prevent lateral movement and data exfiltration.",
        "{target} enables privilege escalation in {product} through path traversal in the {desc} management interface. "
        "ThreatLens recommends urgent patching and review of access control policies on exposed management planes.",
        "{target} exposes a deserialization flaw in {product} that allows authenticated attackers to execute arbitrary commands on the {desc}. "
        "Organizations should restrict network access and apply vendor patches within 24 hours.",
        "{target} in {product} allows credential bypass via crafted authentication tokens against the {desc} API. "
        "Rotate all service credentials and enforce MFA on administrative endpoints immediately.",
    ],
    "shodan": [
        "{target} exposes {product} ({desc}) on the public internet with {port_count} open ports including high-risk services. "
        "ThreatLens recommends immediate firewall rule review and network segmentation to limit blast radius.",
        "{target} is running an outdated {product} ({desc}) with known CVEs on publicly reachable ports. "
        "Enforce TLS, apply security patches, and restrict access to management interfaces behind a VPN.",
    ],
    "github": [
        "{target} identifies a critical supply-chain vulnerability in {product} ({desc}) that may allow dependency confusion attacks. "
        "Review package lockfiles, pin versions, and audit CI/CD pipeline integrity across affected repositories.",
        "{target} discloses a high-severity flaw in {product} ({desc}) enabling arbitrary code execution during build. "
        "Upgrade to the latest patched version and scan downstream consumers for compromised artifacts.",
    ],
    "hibp": [
        "{target} appears in a breach of {product} ({desc}) exposing employee credentials and PII across {breach_count} incidents. "
        "Enforce password resets, enable MFA, and monitor for credential-stuffing attempts on corporate SSO.",
        "{target} has been affected by a data leak in {product} ({desc}) with {breach_count} breach records. "
        "ThreatLens recommends dark-web monitoring and proactive user notification to reduce account takeover risk.",
    ],
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
    total = len(severities)
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
        # Spread timestamps evenly over 72 hours
        minutes_back = int((idx / max(total - 1, 1)) * 72 * 60)
        timestamp = now - timedelta(minutes=minutes_back)
        port = random.choice([22, 80, 443, 3389, 5985, 6379, 9200, 8443, 27017, 8080]) if source == "shodan" else None
        product_idx = random.randint(0, len(PRODUCTS[source]) - 1)
        product, desc = PRODUCTS[source][product_idx]
        summary_template = random.choice(SUMMARIES[source])
        ai_summary = summary_template.format(
            target=target,
            product=product,
            desc=desc,
            port_count=random.randint(2, 7),
            breach_count=random.randint(2, 12),
        )
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
                    "business_unit": random.choice([
                        "payments", "identity", "platform", "data",
                        "infrastructure", "compliance", "engineering", "security-ops",
                    ]),
                    "ports": [port] if port else [],
                    "affected_products": [product],
                    "product_description": desc,
                },
                ai_summary=ai_summary,
                status=decision,
                triage_latency_ms=random.randint(260, 1800),
                langfuse_trace_id=uuid.uuid4().hex,
            )
        )
    db.insert_threats(events)
    cves = [
        CveIntel(
            cve_id="CVE-2024-21762",
            published_date=now - timedelta(hours=4),
            cvss_score=9.8,
            description="Out-of-bounds write in Fortinet FortiOS SSL VPN allows unauthenticated remote code execution via crafted HTTP requests.",
            affected_products=["Fortinet FortiOS", "FortiProxy"],
            ai_triage_notes="Internet-facing FortiOS SSL VPN instances should be patched immediately. Verify WAF and IDS signatures are updated.",
        ),
        CveIntel(
            cve_id="CVE-2024-3400",
            published_date=now - timedelta(hours=9),
            cvss_score=10.0,
            description="Command injection in Palo Alto PAN-OS GlobalProtect allows unauthenticated attackers to execute arbitrary OS commands with root privileges.",
            affected_products=["Palo Alto PAN-OS", "GlobalProtect Gateway"],
            ai_triage_notes="Actively exploited in the wild. Apply vendor hotfix, disable GlobalProtect telemetry, and hunt for indicators of compromise.",
        ),
        CveIntel(
            cve_id="CVE-2024-23897",
            published_date=now - timedelta(hours=15),
            cvss_score=9.1,
            description="Arbitrary file read vulnerability in Jenkins CLI allows unauthenticated attackers to read first few lines of files on the controller filesystem.",
            affected_products=["Jenkins CI", "Jenkins LTS"],
            ai_triage_notes="Restrict CLI access, upgrade Jenkins, and audit build secrets that may have been exposed through file reads.",
        ),
        CveIntel(
            cve_id="CVE-2024-6387",
            published_date=now - timedelta(hours=22),
            cvss_score=8.1,
            description="Race condition in OpenSSH sshd signal handler allows unauthenticated remote code execution on glibc-based Linux systems (regreSSHion).",
            affected_products=["OpenSSH", "Linux servers"],
            ai_triage_notes="Patch OpenSSH to 9.8p1+. Monitor for exploit attempts targeting LoginGraceTime window. Consider reducing MaxStartups.",
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
