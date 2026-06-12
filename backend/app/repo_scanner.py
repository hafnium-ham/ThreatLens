import asyncio
import json
import re
import time
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .config import Settings
from .database import ClickHouse
from .observability import LangfuseTracer


DEPENDENCY_FILES = {
    "package.json": "npm",
    "requirements.txt": "PyPI",
    "Pipfile": "PyPI",
    "go.mod": "Go",
    "Cargo.toml": "crates.io",
    "pom.xml": "Maven",
    "build.gradle": "Maven",
    "composer.json": "Packagist",
    "Gemfile": "RubyGems",
}


class ScanHub:
    def __init__(self):
        self.connections: dict[str, set[Any]] = {}

    async def connect(self, scan_id: str, websocket: Any) -> None:
        await websocket.accept()
        self.connections.setdefault(scan_id, set()).add(websocket)

    def disconnect(self, scan_id: str, websocket: Any) -> None:
        self.connections.get(scan_id, set()).discard(websocket)

    async def broadcast(self, scan_id: str, message: dict[str, Any]) -> None:
        stale = []
        for websocket in self.connections.get(scan_id, set()):
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(scan_id, websocket)


class RepoScanner:
    def __init__(self, settings: Settings, db: ClickHouse, tracer: LangfuseTracer, hub: ScanHub):
        self.settings = settings
        self.db = db
        self.tracer = tracer
        self.hub = hub
        self.status: dict[str, dict[str, Any]] = {}
        self._locks: dict[str, asyncio.Task] = {}


    async def _resolve_username(self, query: str) -> str:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "ThreatLens"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            if " " not in query:
                try:
                    res = await client.get(f"https://api.github.com/users/{urllib.parse.quote(query)}")
                    if res.status_code == 200:
                        return res.json()["login"]
                except Exception:
                    pass
            
            try:
                # Search across users and orgs
                res = await client.get("https://api.github.com/search/users", params={"q": query})
                if res.status_code == 200:
                    data = res.json()
                    if data.get("items"):
                        # Prioritize orgs
                        for item in data["items"]:
                            if item.get("type") == "Organization":
                                return item["login"]
                        return data["items"][0]["login"]
            except Exception:
                pass
                
        return query

    async def start_scan(self, username: str) -> dict[str, Any]:
        username = username.strip().strip("/")
        resolved_username = await self._resolve_username(username)
        username = resolved_username

        scan_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        state = {
            "scan_id": scan_id,
            "username": username,
            "timestamp": now,
            "repos_total": 0,
            "repos_scanned": 0,
            "vulns_found": 0,
            "status": "scanning",
            "duration_ms": 0,
        }
        self.status[scan_id] = {**state, "timestamp": now.isoformat()}
        self.db.insert_repo_scan_status(state)
        self._locks[scan_id] = asyncio.create_task(self._run_scan(scan_id, username, now))
        return {"scan_id": scan_id, "repos_found": 0, "status": "scanning", "resolved_username": username}

    async def _run_scan(self, scan_id: str, username: str, started: datetime) -> None:
        trace_id = self.tracer.trace_id()
        trace = self.tracer.create_trace(trace_id, "repo-scan", {"username": username}, ["repo-scan", f"username:{username}"])
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "ThreatLens"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
                repos = await self._fetch_repos(client, username)
                inventory = [self._inventory_row(scan_id, username, repo) for repo in repos]
                self.db.insert_repo_inventory(inventory)
                await self._update(scan_id, username, started, len(repos), 0, 0, "scanning")
                total_vulns = 0
                critical_count = 0
                for index, repo in enumerate(repos, start=1):
                    deps = await self._dependencies_for_repo(client, username, repo["name"])
                    vulns = await self._vulns_for_repo(client, scan_id, username, repo, deps, trace)
                    total_vulns += len(vulns)
                    critical_count += sum(1 for vuln in vulns if vuln["severity"] == "CRITICAL")
                    self.db.insert_repo_vulns(vulns)
                    await self._update(scan_id, username, started, len(repos), index, total_vulns, "scanning")
                    await self.hub.broadcast(
                        scan_id,
                        {
                            "repo": repo["name"],
                            "deps_found": len(deps),
                            "vulns_found": len(vulns),
                            "status": "scanned",
                            "repos_scanned": index,
                            "repos_total": len(repos),
                        },
                    )
                await self._update(scan_id, username, started, len(repos), len(repos), total_vulns, "complete")
                self.tracer.score(trace, "vuln_count", total_vulns, "Repository vulnerabilities found")
                self.tracer.score(trace, "critical_count", critical_count, "Critical repository vulnerabilities found")
                if trace:
                    with_trace = getattr(trace, "update", None)
                    if callable(with_trace):
                        with_trace(metadata={"username": username, "repo_count": len(repos), "vuln_count": total_vulns, "critical_count": critical_count})
                self.tracer.flush()
                await self.hub.broadcast(scan_id, {"status": "complete", "vulns_found": total_vulns, "repos_total": len(repos)})
        except Exception as exc:
            import traceback
            traceback.print_exc()
            await self._update(scan_id, username, started, self.status.get(scan_id, {}).get("repos_total", 0), self.status.get(scan_id, {}).get("repos_scanned", 0), self.status.get(scan_id, {}).get("vulns_found", 0), "error")
            await self.hub.broadcast(scan_id, {"status": "error", "error": type(exc).__name__})

    async def _fetch_repos(self, client: httpx.AsyncClient, username: str) -> list[dict[str, Any]]:
        urls = [
            f"https://api.github.com/users/{username}/repos",
            f"https://api.github.com/orgs/{username}/repos",
        ]
        for url in urls:
            response = await client.get(url, params={"per_page": 100, "sort": "updated", "direction": "desc"})
            if response.status_code == 200:
                return response.json()
        response.raise_for_status()
        return []

    async def _dependencies_for_repo(self, client: httpx.AsyncClient, username: str, repo: str) -> list[dict[str, str]]:
        deps: list[dict[str, str]] = []
        for branch in ("main", "master"):
            branch_deps = []
            for filename, ecosystem in DEPENDENCY_FILES.items():
                url = f"https://raw.githubusercontent.com/{username}/{repo}/{branch}/{filename}"
                response = await client.get(url)
                if response.status_code == 200:
                    try:
                        branch_deps.extend(parse_dependencies(filename, ecosystem, response.text))
                    except Exception:
                        continue
            if branch_deps:
                deps.extend(branch_deps)
                break
        seen = set()
        deduped = []
        for dep in deps:
            key = (dep["ecosystem"], dep["name"], dep.get("version", ""))
            if key not in seen:
                seen.add(key)
                deduped.append(dep)
        return deduped[:80]

    async def _vulns_for_repo(
        self,
        client: httpx.AsyncClient,
        scan_id: str,
        username: str,
        repo: dict[str, Any],
        deps: list[dict[str, str]],
        trace: Any,
    ) -> list[dict[str, Any]]:
        rows = []
        semaphore = asyncio.Semaphore(8)

        async def check(dep: dict[str, str]) -> list[dict[str, Any]]:
            async with semaphore:
                return await self._query_osv(client, dep, trace)

        results = await asyncio.gather(*(check(dep) for dep in deps), return_exceptions=True)
        for dep, result in zip(deps, results):
            if isinstance(result, Exception):
                continue
            for vuln in result[:8]:
                row = self._vuln_row(scan_id, username, repo, dep, vuln)
                rows.append(row)
        return rows

    async def _query_osv(self, client: httpx.AsyncClient, dep: dict[str, str], trace: Any) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"package": {"name": dep["name"], "ecosystem": dep["ecosystem"]}}
        if dep.get("version"):
            payload["version"] = dep["version"]
        start = time.perf_counter()
        data: dict[str, Any] = {"vulns": []}
        last_error = ""
        for attempt in range(3):
            try:
                response = await client.post("https://api.osv.dev/v1/query", json=payload)
                latency_ms = int((time.perf_counter() - start) * 1000)
                response.raise_for_status()
                data = response.json()
                break
            except Exception as exc:
                last_error = type(exc).__name__
                if attempt == 2:
                    latency_ms = int((time.perf_counter() - start) * 1000)
                else:
                    await asyncio.sleep(0.4 * (2**attempt))
        self.tracer.generation(
            trace,
            "osv-package-query",
            "osv-api",
            payload,
            {"vulns": len(data.get("vulns", [])), "package": dep["name"], "error": last_error},
            {},
            {"generation_type": "osv-api-call", "ecosystem": dep["ecosystem"], "package": dep["name"]},
            latency_ms,
        )
        return data.get("vulns", [])

    async def _update(self, scan_id: str, username: str, started: datetime, total: int, scanned: int, vulns: int, status: str) -> None:
        now = datetime.now(timezone.utc)
        state = {
            "scan_id": scan_id,
            "username": username,
            "timestamp": now,
            "repos_total": total,
            "repos_scanned": scanned,
            "vulns_found": vulns,
            "status": status,
            "duration_ms": int((now - started).total_seconds() * 1000),
        }
        self.status[scan_id] = {**state, "timestamp": now.isoformat()}
        self.db.insert_repo_scan_status(state)

    @staticmethod
    def _inventory_row(scan_id: str, username: str, repo: dict[str, Any]) -> dict[str, Any]:
        return {
            "scan_id": scan_id,
            "username": username,
            "repo_name": repo["name"],
            "repo_url": repo.get("html_url") or f"https://github.com/{username}/{repo['name']}",
            "language": repo.get("language") or "Unknown",
            "stars": repo.get("stargazers_count") or 0,
            "updated_at": parse_dt(repo.get("updated_at")),
        }

    def _vuln_row(self, scan_id: str, username: str, repo: dict[str, Any], dep: dict[str, str], vuln: dict[str, Any]) -> dict[str, Any]:
        score = cvss_score(vuln)
        severity = severity_from_score(score)
        vuln_id = vuln.get("id") or (vuln.get("aliases") or ["UNKNOWN"])[0]
        fix = fixed_version(vuln, dep["name"])
        description = (vuln.get("summary") or vuln.get("details") or "Package vulnerability detected.")[:1200]
        repo_name = repo["name"]
        return {
            "id": uuid.uuid4().hex,
            "scan_id": scan_id,
            "username": username,
            "repo_name": repo_name,
            "repo_url": repo.get("html_url") or f"https://github.com/{username}/{repo_name}",
            "language": repo.get("language") or "Unknown",
            "stars": repo.get("stargazers_count") or 0,
            "package_name": dep["name"],
            "installed_version": dep.get("version") or "",
            "vuln_id": vuln_id,
            "severity": severity,
            "cvss_score": score,
            "description": description,
            "fix_version": fix,
            "published_date": parse_dt(vuln.get("published")),
            "ai_summary": f"{severity} vulnerability {vuln_id} affects {repo_name} through {dep['name']}. Upgrade {dep['name']} to {fix or 'a patched release'} to reduce exposure.",
        }


def parse_dependencies(filename: str, ecosystem: str, content: str) -> list[dict[str, str]]:
    parsers = {
        "package.json": parse_package_json,
        "requirements.txt": parse_requirements,
        "Pipfile": parse_pipfile,
        "go.mod": parse_go_mod,
        "Cargo.toml": parse_toml_like,
        "pom.xml": parse_pom,
        "build.gradle": parse_gradle,
        "composer.json": parse_composer,
        "Gemfile": parse_gemfile,
    }
    if filename.endswith(".csproj"):
        return parse_csproj(content)
    return parsers.get(filename, lambda _content: []) (content)


def parse_package_json(content: str) -> list[dict[str, str]]:
    data = json.loads(content)
    deps = []
    for section in ("dependencies", "devDependencies"):
        for name, version in (data.get(section) or {}).items():
            deps.append({"name": name, "version": clean_version(str(version)), "ecosystem": "npm"})
    return deps


def parse_requirements(content: str) -> list[dict[str, str]]:
    deps = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = re.match(r"([A-Za-z0-9_.-]+)\s*(?:==|>=|~=|<=|>|<)?\s*([A-Za-z0-9_.!*+-]*)", line)
        if match:
            deps.append({"name": match.group(1), "version": clean_version(match.group(2)), "ecosystem": "PyPI"})
    return deps


def parse_pipfile(content: str) -> list[dict[str, str]]:
    deps = []
    for line in content.splitlines():
        match = re.match(r'^([A-Za-z0-9_.-]+)\s*=\s*["\']?([^"\']+)', line.strip())
        if match and match.group(1) not in {"python_version", "python_full_version"}:
            deps.append({"name": match.group(1), "version": clean_version(match.group(2)), "ecosystem": "PyPI"})
    return deps


def parse_go_mod(content: str) -> list[dict[str, str]]:
    deps = []
    for line in content.splitlines():
        line = line.strip()
        match = re.match(r"([A-Za-z0-9_./-]+\.[A-Za-z0-9_./-]+)\s+(v[0-9][^\s]+)", line)
        if match:
            deps.append({"name": match.group(1), "version": match.group(2), "ecosystem": "Go"})
    return deps


def parse_toml_like(content: str) -> list[dict[str, str]]:
    deps = []
    for line in content.splitlines():
        match = re.match(r'^([A-Za-z0-9_-]+)\s*=\s*["\']?([^"\'}]+)', line.strip())
        if match:
            deps.append({"name": match.group(1), "version": clean_version(match.group(2)), "ecosystem": "crates.io"})
    return deps


def parse_pom(content: str) -> list[dict[str, str]]:
    deps = []
    for block in re.findall(r"<dependency>(.*?)</dependency>", content, re.DOTALL):
        group = tag(block, "groupId")
        artifact = tag(block, "artifactId")
        version = tag(block, "version")
        if group and artifact:
            deps.append({"name": f"{group}:{artifact}", "version": clean_version(version), "ecosystem": "Maven"})
    return deps


def parse_gradle(content: str) -> list[dict[str, str]]:
    deps = []
    for group, artifact, version in re.findall(r"['\"]([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+):([^'\"]+)['\"]", content):
        deps.append({"name": f"{group}:{artifact}", "version": clean_version(version), "ecosystem": "Maven"})
    return deps


def parse_composer(content: str) -> list[dict[str, str]]:
    data = json.loads(content)
    deps = []
    for section in ("require", "require-dev"):
        for name, version in (data.get(section) or {}).items():
            if name != "php":
                deps.append({"name": name, "version": clean_version(str(version)), "ecosystem": "Packagist"})
    return deps


def parse_gemfile(content: str) -> list[dict[str, str]]:
    deps = []
    for name, version in re.findall(r"gem ['\"]([^'\"]+)['\"](?:,\s*['\"]([^'\"]+)['\"])?", content):
        deps.append({"name": name, "version": clean_version(version), "ecosystem": "RubyGems"})
    return deps


def parse_csproj(content: str) -> list[dict[str, str]]:
    deps = []
    for name, version in re.findall(r'<PackageReference[^>]+Include=["\']([^"\']+)["\'][^>]+Version=["\']([^"\']+)["\']', content):
        deps.append({"name": name, "version": clean_version(version), "ecosystem": "NuGet"})
    return deps


def tag(block: str, name: str) -> str:
    match = re.search(rf"<{name}>(.*?)</{name}>", block)
    return match.group(1).strip() if match else ""


def clean_version(version: str) -> str:
    return re.sub(r"^[~^<>=! ]+", "", version or "").strip()


def cvss_score(vuln: dict[str, Any]) -> float:
    scores = []
    for severity in vuln.get("severity") or []:
        if severity.get("type", "").upper().startswith("CVSS"):
            match = re.search(r"/AV:|CVSS:", severity.get("score", ""))
            if match:
                vector = severity.get("score", "")
                score_match = re.search(r"(\d+\.\d+)$", vector)
                if score_match:
                    scores.append(float(score_match.group(1)))
    database_score = vuln.get("database_specific", {}).get("cvss_score")
    if database_score:
        scores.append(float(database_score))
    return max(scores) if scores else 7.5


def severity_from_score(score: float) -> str:
    if score >= 9:
        return "CRITICAL"
    if score >= 7:
        return "HIGH"
    if score >= 4:
        return "MEDIUM"
    return "LOW"


def fixed_version(vuln: dict[str, Any], package_name: str) -> str:
    for affected in vuln.get("affected") or []:
        if affected.get("package", {}).get("name") != package_name:
            continue
        for event in affected.get("ranges", [{}])[0].get("events", []):
            if event.get("fixed"):
                return event["fixed"]
    return ""


def parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def seed_repo_demo_data(db: ClickHouse) -> None:
    if db.repo_vuln_count() > 0:
        return
    scan_id = "demo-facebook-scan"
    now = datetime.now(timezone.utc)
    repos = [
        ("react", "JavaScript", 240000, 8, 3),
        ("jest", "TypeScript", 45000, 5, 1),
        ("docusaurus", "TypeScript", 61000, 4, 0),
        ("relay", "JavaScript", 19000, 2, 0),
        ("watchman", "C++", 13000, 1, 0),
        ("folly", "C++", 29000, 0, 0),
        ("zstd", "C", 24000, 1, 0),
        ("rocksdb", "C++", 30000, 2, 1),
    ]
    inventory = [
        {
            "scan_id": scan_id,
            "username": "facebook",
            "repo_name": name,
            "repo_url": f"https://github.com/facebook/{name}",
            "language": language,
            "stars": stars,
            "updated_at": now - timedelta(days=index),
        }
        for index, (name, language, stars, _, _) in enumerate(repos)
    ]
    db.insert_repo_inventory(inventory)
    vulns = []
    packages = ["lodash", "minimist", "webpack", "axios", "serialize-javascript", "shell-quote", "tar", "node-forge"]
    for repo_index, (repo, language, stars, vuln_count, critical_count) in enumerate(repos):
        for index in range(vuln_count):
            score = 9.8 if index < critical_count else [8.1, 7.5, 6.4, 5.3][index % 4]
            severity = severity_from_score(score)
            package = packages[(repo_index + index) % len(packages)]
            vuln_id = f"CVE-2024-{12000 + repo_index * 17 + index}"
            vulns.append(
                {
                    "id": uuid.uuid4().hex,
                    "scan_id": scan_id,
                    "username": "facebook",
                    "repo_name": repo,
                    "repo_url": f"https://github.com/facebook/{repo}",
                    "language": language,
                    "stars": stars,
                    "package_name": package,
                    "installed_version": "1.0.0",
                    "vuln_id": vuln_id,
                    "severity": severity,
                    "cvss_score": score,
                    "description": f"{package} contains a known vulnerability that can affect repository build or runtime security.",
                    "fix_version": "9.9.9" if severity == "CRITICAL" else "2.0.0",
                    "published_date": now - timedelta(hours=index * 7 + repo_index * 3),
                    "ai_summary": f"{severity} vulnerability {vuln_id} affects facebook/{repo} through {package}. Upgrade {package} to a patched release before deployment.",
                }
            )
    db.insert_repo_vulns(vulns)
    db.insert_repo_scan_status(
        {
            "scan_id": scan_id,
            "username": "facebook",
            "timestamp": now,
            "repos_total": len(repos),
            "repos_scanned": len(repos),
            "vulns_found": len(vulns),
            "status": "complete",
            "duration_ms": 8421,
        }
    )
