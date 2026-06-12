import json
import time
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any

import clickhouse_connect

from .config import Settings
from .models import AgentRun, CveIntel, ThreatEvent


SCHEMA = """
CREATE TABLE IF NOT EXISTS threat_events
(
    id String,
    timestamp DateTime64(3, 'UTC'),
    source LowCardinality(String),
    threat_type LowCardinality(String),
    target String,
    severity UInt8,
    raw_data String,
    ai_summary String,
    status LowCardinality(String),
    triage_latency_ms UInt32 DEFAULT 0,
    langfuse_trace_id String DEFAULT ''
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, severity, source, id)
TTL toDateTime(timestamp) + INTERVAL 365 DAY;

CREATE TABLE IF NOT EXISTS agent_runs
(
    id String,
    timestamp DateTime64(3, 'UTC'),
    duration_ms UInt32,
    threats_found UInt32,
    model_used LowCardinality(String),
    langfuse_trace_id String,
    status LowCardinality(String) DEFAULT 'success',
    severity_breakdown String DEFAULT '{}'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, id);

CREATE TABLE IF NOT EXISTS cve_intel
(
    cve_id String,
    published_date DateTime64(3, 'UTC'),
    cvss_score Float32,
    description String,
    affected_products Array(String),
    ai_triage_notes String
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(published_date)
ORDER BY cve_id;

CREATE TABLE IF NOT EXISTS repo_scans
(
    scan_id String,
    username String,
    timestamp DateTime64(3, 'UTC'),
    repos_total UInt32,
    repos_scanned UInt32,
    vulns_found UInt32,
    status LowCardinality(String),
    duration_ms UInt32
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (username, scan_id, timestamp);

CREATE TABLE IF NOT EXISTS repo_inventory
(
    scan_id String,
    username String,
    repo_name String,
    repo_url String,
    language LowCardinality(String),
    stars UInt32,
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree
ORDER BY (username, repo_name);

CREATE TABLE IF NOT EXISTS repo_vulns
(
    id String,
    scan_id String,
    username String,
    repo_name String,
    repo_url String,
    language LowCardinality(String),
    stars UInt32,
    package_name String,
    installed_version String,
    vuln_id String,
    severity LowCardinality(String),
    cvss_score Float32,
    description String,
    fix_version String,
    published_date DateTime64(3, 'UTC'),
    ai_summary String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(published_date)
ORDER BY (username, repo_name, severity, vuln_id);
"""


class ClickHouse:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = None

    def connect(self) -> None:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                self.client = clickhouse_connect.get_client(
                    host=self.settings.clickhouse_host,
                    port=self.settings.clickhouse_port,
                    username=self.settings.clickhouse_user,
                    password=self.settings.clickhouse_password,
                    database=self.settings.clickhouse_database,
                    secure=self.settings.clickhouse_secure or self.settings.clickhouse_port == 8443,
                    autogenerate_session_id=False,
                    connect_timeout=5,
                )
                self.ensure_schema()
                return
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"ClickHouse connection failed: {last_error}") from last_error

    def ensure_schema(self) -> None:
        assert self.client is not None
        for statement in [part.strip() for part in SCHEMA.split(";") if part.strip()]:
            self.client.command(statement)
        self.client.command("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS status LowCardinality(String) DEFAULT 'success'")
        self.client.command("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS severity_breakdown String DEFAULT '{}'")

    def insert_repo_scan_status(self, scan: dict[str, Any]) -> None:
        assert self.client is not None
        self.client.insert(
            "repo_scans",
            [[
                scan["scan_id"],
                scan["username"],
                scan["timestamp"],
                scan["repos_total"],
                scan["repos_scanned"],
                scan["vulns_found"],
                scan["status"],
                scan["duration_ms"],
            ]],
            column_names=[
                "scan_id",
                "username",
                "timestamp",
                "repos_total",
                "repos_scanned",
                "vulns_found",
                "status",
                "duration_ms",
            ],
        )

    def insert_repo_inventory(self, repos: list[dict[str, Any]]) -> None:
        if not repos:
            return
        assert self.client is not None
        self.client.insert(
            "repo_inventory",
            [
                [
                    repo["scan_id"],
                    repo["username"],
                    repo["repo_name"],
                    repo["repo_url"],
                    repo.get("language") or "Unknown",
                    int(repo.get("stars") or 0),
                    repo["updated_at"],
                ]
                for repo in repos
            ],
            column_names=["scan_id", "username", "repo_name", "repo_url", "language", "stars", "updated_at"],
        )

    def insert_repo_vulns(self, vulns: list[dict[str, Any]]) -> None:
        if not vulns:
            return
        assert self.client is not None
        self.client.insert(
            "repo_vulns",
            [
                [
                    vuln["id"],
                    vuln["scan_id"],
                    vuln["username"],
                    vuln["repo_name"],
                    vuln["repo_url"],
                    vuln.get("language") or "Unknown",
                    int(vuln.get("stars") or 0),
                    vuln["package_name"],
                    vuln.get("installed_version") or "",
                    vuln["vuln_id"],
                    vuln["severity"],
                    float(vuln.get("cvss_score") or 0),
                    vuln.get("description") or "",
                    vuln.get("fix_version") or "",
                    vuln["published_date"],
                    vuln.get("ai_summary") or "",
                ]
                for vuln in vulns
            ],
            column_names=[
                "id",
                "scan_id",
                "username",
                "repo_name",
                "repo_url",
                "language",
                "stars",
                "package_name",
                "installed_version",
                "vuln_id",
                "severity",
                "cvss_score",
                "description",
                "fix_version",
                "published_date",
                "ai_summary",
            ],
        )

    def repo_scan_status(self, scan_id: str) -> dict[str, Any] | None:
        assert self.client is not None
        result = self.client.query(
            """
            SELECT scan_id, username, timestamp, repos_total, repos_scanned, vulns_found, status, duration_ms
            FROM repo_scans
            WHERE scan_id = {scan_id:String}
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            parameters={"scan_id": scan_id},
        )
        if not result.result_rows:
            return None
        row = result.result_rows[0]
        return {
            "scan_id": row[0],
            "username": row[1],
            "timestamp": self._iso(row[2]),
            "repos_total": row[3],
            "repos_scanned": row[4],
            "vulns_found": row[5],
            "status": row[6],
            "duration_ms": row[7],
        }

    def repos_for_user(self, username: str) -> list[dict[str, Any]]:
        assert self.client is not None
        result = self.client.query(
            """
            WITH vuln_rollup AS
            (
                SELECT
                    repo_name,
                    count() AS vuln_count,
                    countIf(severity = 'CRITICAL') AS critical,
                    countIf(severity = 'HIGH') AS high,
                    countIf(severity = 'MEDIUM') AS medium,
                    countIf(severity = 'LOW') AS low,
                    max(cvss_score) AS worst_score
                FROM repo_vulns
                WHERE username = {username:String}
                GROUP BY repo_name
            )
            SELECT
                inv.repo_name,
                anyLast(inv.repo_url) AS repo_url,
                anyLast(inv.language) AS language,
                anyLast(inv.stars) AS stars,
                max(inv.updated_at) AS updated_at,
                ifNull(any(v.vuln_count), 0) AS vuln_count,
                ifNull(any(v.critical), 0) AS critical,
                ifNull(any(v.high), 0) AS high,
                ifNull(any(v.medium), 0) AS medium,
                ifNull(any(v.low), 0) AS low,
                ifNull(any(v.worst_score), 0) AS worst_score
            FROM repo_inventory AS inv
            LEFT JOIN vuln_rollup AS v ON inv.repo_name = v.repo_name
            WHERE inv.username = {username:String}
            GROUP BY inv.repo_name
            ORDER BY vuln_count DESC, worst_score DESC, stars DESC
            """,
            parameters={"username": username},
        )
        return [
            {
                "repo_name": row[0],
                "repo_url": row[1],
                "language": row[2],
                "stars": row[3],
                "updated_at": self._iso(row[4]),
                "vuln_count": row[5],
                "severity_breakdown": {"critical": row[6], "high": row[7], "medium": row[8], "low": row[9]},
                "worst_score": row[10],
                "worst_severity": self._severity_from_score(row[10]),
            }
            for row in result.result_rows
        ]

    def repo_vulns(self, username: str, repo_name: str) -> list[dict[str, Any]]:
        assert self.client is not None
        result = self.client.query(
            """
            SELECT package_name, installed_version, vuln_id, severity, cvss_score,
                   description, fix_version, published_date, ai_summary
            FROM repo_vulns
            WHERE username = {username:String} AND repo_name = {repo_name:String}
            ORDER BY cvss_score DESC, published_date DESC
            """,
            parameters={"username": username, "repo_name": repo_name},
        )
        return [
            {
                "package_name": row[0],
                "installed_version": row[1],
                "vuln_id": row[2],
                "severity": row[3],
                "cvss_score": row[4],
                "description": row[5],
                "fix_version": row[6],
                "published_date": self._iso(row[7]),
                "ai_summary": row[8],
                "recommendation": f"FIX: upgrade {row[0]} to {row[6]}" if row[6] else f"FIX: review advisory for {row[0]}",
            }
            for row in result.result_rows
        ]

    def latest_repo_vulns(self, limit: int = 100) -> list[dict[str, Any]]:
        assert self.client is not None
        result = self.client.query(
            """
            SELECT vuln_id, package_name, installed_version, severity, cvss_score,
                   description, published_date, repo_name, username
            FROM repo_vulns
            ORDER BY published_date DESC
            LIMIT {limit:UInt32}
            """,
            parameters={"limit": limit},
        )
        return [
            {
                "vuln_id": row[0],
                "package_name": row[1],
                "installed_version": row[2],
                "severity": row[3],
                "cvss_score": row[4],
                "description": row[5],
                "published_date": self._iso(row[6]),
                "repo_name": row[7],
                "username": row[8],
            }
            for row in result.result_rows
        ]

    def repo_analytics(self, username: str) -> dict[str, Any]:
        repos = self.repos_for_user(username)
        total_vulns = sum(repo["vuln_count"] for repo in repos)
        critical = sum(repo["severity_breakdown"]["critical"] for repo in repos)
        most_affected = repos[0]["repo_name"] if repos else "none"
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for repo in repos:
            for key, value in repo["severity_breakdown"].items():
                severity_counts[key] += value
        seven_day = self.client.query(
            """
            SELECT toDate(published_date) AS day, count()
            FROM repo_vulns
            WHERE username = {username:String} AND published_date >= now() - INTERVAL 7 DAY
            GROUP BY day
            ORDER BY day ASC
            """,
            parameters={"username": username},
        ).result_rows
        return {
            "total_repos": len(repos),
            "total_vulns": total_vulns,
            "critical_count": critical,
            "most_affected_repo": most_affected,
            "severity_counts": severity_counts,
            "vulns_over_time": [{"day": str(row[0]), "count": row[1]} for row in seven_day],
        }

    def repo_vuln_count(self) -> int:
        assert self.client is not None
        with suppress(Exception):
            return int(self.client.query("SELECT count() FROM repo_vulns").first_row[0])
        return 0

    def insert_threats(self, events: list[ThreatEvent]) -> None:
        if not events:
            return
        assert self.client is not None
        rows = [
            [
                event.id,
                event.timestamp,
                event.source,
                event.threat_type,
                event.target,
                event.severity,
                json.dumps(event.raw_data, default=str),
                event.ai_summary,
                event.status,
                event.triage_latency_ms,
                event.langfuse_trace_id,
            ]
            for event in events
        ]
        self.client.insert(
            "threat_events",
            rows,
            column_names=[
                "id",
                "timestamp",
                "source",
                "threat_type",
                "target",
                "severity",
                "raw_data",
                "ai_summary",
                "status",
                "triage_latency_ms",
                "langfuse_trace_id",
            ],
        )

    def insert_agent_run(self, run: AgentRun) -> None:
        assert self.client is not None
        self.client.insert(
            "agent_runs",
            [
                [
                    run.id,
                    run.timestamp,
                    run.duration_ms,
                    run.threats_found,
                    run.model_used,
                    run.langfuse_trace_id,
                    run.status,
                    json.dumps(run.severity_breakdown),
                ]
            ],
            column_names=[
                "id",
                "timestamp",
                "duration_ms",
                "threats_found",
                "model_used",
                "langfuse_trace_id",
                "status",
                "severity_breakdown",
            ],
        )

    def upsert_cves(self, cves: list[CveIntel]) -> None:
        if not cves:
            return
        assert self.client is not None
        self.client.insert(
            "cve_intel",
            [
                [
                    cve.cve_id,
                    cve.published_date,
                    cve.cvss_score,
                    cve.description,
                    cve.affected_products,
                    cve.ai_triage_notes,
                ]
                for cve in cves
            ],
            column_names=[
                "cve_id",
                "published_date",
                "cvss_score",
                "description",
                "affected_products",
                "ai_triage_notes",
            ],
        )

    def recent_threats(self, limit: int = 50, severity_min: int = 1) -> list[dict[str, Any]]:
        assert self.client is not None
        result = self.client.query(
            """
            SELECT id, timestamp, source, threat_type, target, severity, raw_data, ai_summary,
                   status, triage_latency_ms, langfuse_trace_id
            FROM threat_events
            WHERE severity >= {severity_min:UInt8}
            ORDER BY timestamp DESC
            LIMIT {limit:UInt32}
            """,
            parameters={"severity_min": severity_min, "limit": limit},
        )
        return [self._threat_row(row) for row in result.result_rows]

    def analytics_summary(self) -> dict[str, Any]:
        assert self.client is not None
        total = self.client.query("SELECT count(), avg(severity), max(timestamp) FROM threat_events").first_row
        by_source = self.client.query(
            "SELECT source, count() FROM threat_events GROUP BY source ORDER BY count() DESC"
        ).result_rows
        by_status = self.client.query(
            "SELECT status, count() FROM threat_events GROUP BY status ORDER BY count() DESC"
        ).result_rows
        severity_series = self.client.query(
            """
            SELECT toStartOfHour(timestamp) AS hour, severity, count()
            FROM threat_events
            WHERE timestamp >= now() - INTERVAL 48 HOUR
            GROUP BY hour, severity
            ORDER BY hour ASC, severity ASC
            """
        ).result_rows
        triage_latency = self.client.query(
            """
            SELECT toStartOfHour(timestamp) AS hour, avg(triage_latency_ms), quantile(0.95)(triage_latency_ms)
            FROM threat_events
            WHERE triage_latency_ms > 0
            GROUP BY hour
            ORDER BY hour ASC
            """
        ).result_rows
        mean_latency = self.client.query("SELECT avg(triage_latency_ms) FROM threat_events WHERE triage_latency_ms > 0").first_row[0]
        velocity_now = self.client.query("SELECT count() FROM threat_events WHERE timestamp >= now() - INTERVAL 1 HOUR").first_row[0]
        velocity_24h = self.client.query(
            """
            SELECT count()
            FROM threat_events
            WHERE timestamp >= now() - INTERVAL 25 HOUR
              AND timestamp < now() - INTERVAL 24 HOUR
            """
        ).first_row[0]
        benchmark = [
            self._benchmark_query(
                "severity_histogram",
                """
                SELECT severity, count(), avg(triage_latency_ms)
                FROM threat_events
                GROUP BY severity
                ORDER BY severity
                """,
            ),
            self._benchmark_query(
                "source_rollup_72h",
                """
                SELECT source, count(), quantile(0.95)(triage_latency_ms)
                FROM threat_events
                WHERE timestamp >= now() - INTERVAL 72 HOUR
                GROUP BY source
                ORDER BY count() DESC
                """,
            ),
            self._benchmark_query(
                "critical_targets",
                """
                SELECT target, max(severity), count()
                FROM threat_events
                WHERE severity >= 9
                GROUP BY target
                ORDER BY count() DESC
                LIMIT 10
                """,
            ),
        ]
        severity_histogram = benchmark[0]["result"]
        return {
            "total_threats": total[0] or 0,
            "avg_severity": round(float(total[1] or 0), 2),
            "latest_event_at": self._iso(total[2]) if total[2] else None,
            "by_source": [{"source": row[0], "count": row[1]} for row in by_source],
            "by_status": [{"status": row[0], "count": row[1]} for row in by_status],
            "severity_over_time": [
                {"hour": self._iso(row[0]), "severity": row[1], "count": row[2]} for row in severity_series
            ],
            "triage_latency": [
                {"hour": self._iso(row[0]), "avg_ms": round(float(row[1]), 2), "p95_ms": round(float(row[2]), 2)}
                for row in triage_latency
            ],
            "mean_time_to_triage_ms": round(float(mean_latency or 0), 2),
            "threat_velocity": {"current_hour": velocity_now or 0, "same_hour_24h_ago": velocity_24h or 0},
            "query_benchmarks": benchmark,
            "query_performance": {
                "name": "Severity histogram over columnar threat_events",
                "execution_ms": benchmark[0]["execution_ms"],
                "rows_scanned": total[0] or 0,
                "result": [
                    {"severity": row[0], "count": row[1], "avg_triage_ms": round(float(row[2] or 0), 2)}
                    for row in severity_histogram
                ],
            },
        }

    def agent_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        assert self.client is not None
        result = self.client.query(
            """
            SELECT id, timestamp, duration_ms, threats_found, model_used, langfuse_trace_id, status, severity_breakdown
            FROM agent_runs
            ORDER BY timestamp DESC
            LIMIT {limit:UInt32}
            """,
            parameters={"limit": limit},
        )
        return [
            {
                "id": row[0],
                "timestamp": self._iso(row[1]),
                "duration_ms": row[2],
                "threats_found": row[3],
                "model_used": row[4],
                "langfuse_trace_id": row[5],
                "status": row[6],
                "severity_breakdown": json.loads(row[7]) if row[7] else {},
            }
            for row in result.result_rows
        ]

    def search_cves(self, search: str = "", limit: int = 50) -> list[dict[str, Any]]:
        assert self.client is not None
        if search:
            query = """
                SELECT cve_id, published_date, cvss_score, description, affected_products, ai_triage_notes
                FROM cve_intel
                WHERE positionCaseInsensitive(cve_id, {search:String}) > 0
                   OR positionCaseInsensitive(description, {search:String}) > 0
                   OR arrayExists(x -> positionCaseInsensitive(x, {search:String}) > 0, affected_products)
                ORDER BY published_date DESC
                LIMIT {limit:UInt32}
            """
            result = self.client.query(query, parameters={"search": search, "limit": limit})
        else:
            result = self.client.query(
                """
                SELECT cve_id, published_date, cvss_score, description, affected_products, ai_triage_notes
                FROM cve_intel
                ORDER BY published_date DESC
                LIMIT {limit:UInt32}
                """,
                parameters={"limit": limit},
            )
        return [
            {
                "cve_id": row[0],
                "published_date": self._iso(row[1]),
                "cvss_score": row[2],
                "description": row[3],
                "affected_products": row[4],
                "ai_triage_notes": row[5],
            }
            for row in result.result_rows
        ]

    def threat_count(self) -> int:
        assert self.client is not None
        with suppress(Exception):
            return int(self.client.query("SELECT count() FROM threat_events").first_row[0])
        return 0

    def has_data(self) -> bool:
        return self.threat_count() > 0

    def _benchmark_query(self, name: str, query: str) -> dict[str, Any]:
        start = time.perf_counter()
        result = self.client.query(query)
        execution_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"name": name, "execution_ms": execution_ms, "result": result.result_rows}

    def _threat_row(self, row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": row[0],
            "timestamp": self._iso(row[1]),
            "source": row[2],
            "threat_type": row[3],
            "target": row[4],
            "severity": row[5],
            "raw_data": json.loads(row[6]) if row[6] else {},
            "ai_summary": row[7],
            "status": row[8],
            "triage_latency_ms": row[9],
            "langfuse_trace_id": row[10],
        }

    @staticmethod
    def _severity_from_score(score: float) -> str:
        if score >= 9:
            return "CRITICAL"
        if score >= 7:
            return "HIGH"
        if score >= 4:
            return "MEDIUM"
        if score > 0:
            return "LOW"
        return "CLEAN"

    @staticmethod
    def _iso(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
