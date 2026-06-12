import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .config import Settings
from .models import RawThreat


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


class ThreatCollectors:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def collect_all(self) -> list[RawThreat]:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            batches = [
                await self.collect_nvd(client),
                await self.collect_github_advisories(client),
                await self.collect_shodan(client),
                await self.collect_hibp(client),
            ]
        seen: set[str] = set()
        threats: list[RawThreat] = []
        for batch in batches:
            for threat in batch:
                if threat.id not in seen:
                    threats.append(threat)
                    seen.add(threat.id)
        return threats

    async def collect_nvd(self, client: httpx.AsyncClient) -> list[RawThreat]:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=1)
        params = {
            "pubStartDate": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "pubEndDate": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "resultsPerPage": 20,
        }
        headers = {"apiKey": self.settings.nvd_api_key} if self.settings.nvd_api_key else {}
        try:
            response = await client.get("https://services.nvd.nist.gov/rest/json/cves/2.0", params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            threats = []
            for item in data.get("vulnerabilities", [])[:12]:
                cve = item.get("cve", {})
                cve_id = cve.get("id", "unknown-cve")
                published = self._parse_dt(cve.get("published"), now)
                descriptions = cve.get("descriptions", [])
                description = next((d.get("value") for d in descriptions if d.get("lang") == "en"), "")
                metrics = cve.get("metrics", {})
                score = self._cvss(metrics)
                threats.append(
                    RawThreat(
                        id=stable_id("nvd", cve_id),
                        timestamp=published,
                        source="nvd",
                        target=cve_id,
                        raw_data={"cve_id": cve_id, "description": description, "cvss_score": score, "nvd": cve},
                    )
                )
            return threats or self.demo_nvd()
        except Exception:
            return self.demo_nvd()

    async def collect_github_advisories(self, client: httpx.AsyncClient) -> list[RawThreat]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        try:
            response = await client.get(
                "https://api.github.com/advisories",
                params={"per_page": 12, "sort": "published", "direction": "desc"},
                headers=headers,
            )
            response.raise_for_status()
            threats = []
            for item in response.json()[:12]:
                ghsa = item.get("ghsa_id", "unknown-ghsa")
                threats.append(
                    RawThreat(
                        id=stable_id("github", ghsa),
                        timestamp=self._parse_dt(item.get("published_at"), datetime.now(timezone.utc)),
                        source="github",
                        target=ghsa,
                        raw_data={
                            "ghsa_id": ghsa,
                            "cve_id": item.get("cve_id"),
                            "summary": item.get("summary"),
                            "severity": item.get("severity"),
                            "ecosystem": (item.get("vulnerabilities") or [{}])[0].get("package", {}).get("ecosystem"),
                            "advisory": item,
                        },
                    )
                )
            return threats or self.demo_github()
        except Exception:
            return self.demo_github()

    async def collect_shodan(self, client: httpx.AsyncClient) -> list[RawThreat]:
        threats: list[RawThreat] = []
        for ip in self.settings.target_ip_list:
            try:
                response = await client.get(f"https://internetdb.shodan.io/{ip}")
                response.raise_for_status()
                data = response.json()
                if data.get("ports") or data.get("vulns"):
                    threats.append(
                        RawThreat(
                            id=stable_id("shodan", f"{ip}:{data}"),
                            timestamp=datetime.now(timezone.utc),
                            source="shodan",
                            target=ip,
                            raw_data={
                                "ip": ip,
                                "hostnames": data.get("hostnames", []),
                                "ports": data.get("ports", []),
                                "vulns": data.get("vulns", []),
                                "tags": data.get("tags", []),
                            },
                        )
                    )
            except Exception:
                continue
        return threats or self.demo_shodan()

    async def collect_hibp(self, client: httpx.AsyncClient) -> list[RawThreat]:
        if not self.settings.hibp_api_key:
            return self.demo_hibp()
        headers = {"hibp-api-key": self.settings.hibp_api_key, "user-agent": "ThreatLens Demo Agent"}
        threats = []
        for domain in self.settings.demo_domain_list:
            try:
                response = await client.get(f"https://haveibeenpwned.com/api/v3/breacheddomain/{domain}", headers=headers)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                breaches = response.json()
                if breaches:
                    threats.append(
                        RawThreat(
                            id=stable_id("hibp", f"{domain}:{breaches}"),
                            timestamp=datetime.now(timezone.utc),
                            source="hibp",
                            target=domain,
                            raw_data={"domain": domain, "breaches": breaches[:20], "breach_count": len(breaches)},
                        )
                    )
            except Exception:
                continue
        return threats or self.demo_hibp()

    def demo_nvd(self) -> list[RawThreat]:
        now = datetime.now(timezone.utc)
        samples = [
            (
                "CVE-2026-34891",
                "Unauthenticated remote code execution in Apache Struts file upload validation allows crafted multipart requests to execute commands.",
                9.8,
                ["Apache Struts", "Java web applications"],
            ),
            (
                "CVE-2026-31207",
                "Privilege escalation in OpenSSL provider loading permits local attackers to bypass signing policy on misconfigured hosts.",
                7.4,
                ["OpenSSL", "Linux servers"],
            ),
            (
                "CVE-2026-28744",
                "Cross-site scripting in a popular Kubernetes dashboard extension exposes service account tokens to authenticated users.",
                6.5,
                ["Kubernetes dashboard", "Cluster extensions"],
            ),
        ]
        return [
            RawThreat(
                id=stable_id("nvd-demo", cve_id),
                timestamp=now - timedelta(minutes=idx * 17),
                source="nvd",
                target=cve_id,
                raw_data={
                    "cve_id": cve_id,
                    "description": description,
                    "cvss_score": score,
                    "affected_products": products,
                    "demo": True,
                },
            )
            for idx, (cve_id, description, score, products) in enumerate(samples)
        ]

    def demo_github(self) -> list[RawThreat]:
        now = datetime.now(timezone.utc)
        samples = [
            {
                "ghsa_id": "GHSA-demo-9x2p-rce7",
                "summary": "Critical template injection in npm package render-fast enables server-side command execution.",
                "severity": "critical",
                "ecosystem": "npm",
                "package": "render-fast",
            },
            {
                "ghsa_id": "GHSA-demo-4m8q-token",
                "summary": "Python package ci-helper logs cloud deployment tokens during failed builds.",
                "severity": "high",
                "ecosystem": "pip",
                "package": "ci-helper",
            },
        ]
        return [
            RawThreat(
                id=stable_id("github-demo", sample["ghsa_id"]),
                timestamp=now - timedelta(minutes=9 + idx * 21),
                source="github",
                target=sample["ghsa_id"],
                raw_data={**sample, "demo": True},
            )
            for idx, sample in enumerate(samples)
        ]

    def demo_shodan(self) -> list[RawThreat]:
        now = datetime.now(timezone.utc)
        samples = [
            {"ip": "203.0.113.10", "ports": [22, 80, 443, 9200], "vulns": ["CVE-2026-34891"], "tags": ["cloud", "elasticsearch"]},
            {"ip": "198.51.100.24", "ports": [3389, 5985], "vulns": [], "tags": ["rdp", "windows"]},
            {"ip": "192.0.2.45", "ports": [8080, 8443], "vulns": ["CVE-2026-28744"], "tags": ["kubernetes"]},
        ]
        return [
            RawThreat(
                id=stable_id("shodan-demo", f"{sample['ip']}:{sample['ports']}"),
                timestamp=now - timedelta(minutes=idx * 13),
                source="shodan",
                target=sample["ip"],
                raw_data={**sample, "demo": True},
            )
            for idx, sample in enumerate(samples)
        ]

    def demo_hibp(self) -> list[RawThreat]:
        now = datetime.now(timezone.utc)
        domains = self.settings.demo_domain_list or ["example.com"]
        return [
            RawThreat(
                id=stable_id("hibp-demo", domain),
                timestamp=now - timedelta(minutes=31 + idx * 11),
                source="hibp",
                target=domain,
                raw_data={
                    "domain": domain,
                    "breach_count": 2 + idx,
                    "breaches": [
                        {"Name": "DemoCRM", "DataClasses": ["Email addresses", "Passwords", "Phone numbers"]},
                        {"Name": "VendorPortal", "DataClasses": ["Email addresses", "Job titles"]},
                    ],
                    "demo": True,
                },
            )
            for idx, domain in enumerate(domains[:2])
        ]

    @staticmethod
    def _parse_dt(value: str | None, fallback: datetime) -> datetime:
        if not value:
            return fallback
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return fallback

    @staticmethod
    def _cvss(metrics: dict[str, Any]) -> float:
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            values = metrics.get(key)
            if values:
                return float(values[0].get("cvssData", {}).get("baseScore", 0))
        return 0.0
