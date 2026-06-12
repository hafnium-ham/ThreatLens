import asyncio
import csv
import io
import os
import time
from contextlib import asynccontextmanager, suppress

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import FileResponse, StreamingResponse

from .agent import ThreatLensAgent
from .ai import ThreatTriageAI
from .collectors import ThreatCollectors
from .config import get_settings
from .database import ClickHouse
from .models import ThreatEvent
from .observability import LangfuseTracer
from .repo_scanner import RepoScanner, ScanHub, seed_repo_demo_data
from .seed import seed_demo_data


class FeedHub:
    def __init__(self):
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self, event: ThreatEvent) -> None:
        stale: list[WebSocket] = []
        for websocket in self.connections:
            try:
                await websocket.send_json(event.model_dump(mode="json"))
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket)


settings = get_settings()
hub = FeedHub()
scan_hub = ScanHub()
db = ClickHouse(settings)
tracer = LangfuseTracer(settings)
ai = ThreatTriageAI(settings, tracer)
collectors = ThreatCollectors(settings)
agent = ThreatLensAgent(db, collectors, ai, tracer, settings.groq_model, hub.broadcast)
repo_scanner = RepoScanner(settings, db, tracer, scan_hub)
scheduler = AsyncIOScheduler(timezone="UTC")


class GitHubScanRequest(BaseModel):
    username: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect()
    seed_demo_data(db)
    seed_repo_demo_data(db)
    scheduler.add_job(agent.run_once, "interval", minutes=settings.agent_interval_minutes, id="threatlens-agent")
    scheduler.start()
    asyncio.create_task(agent.run_once())
    yield
    scheduler.shutdown(wait=False)
    tracer.flush()


app = FastAPI(title="ThreatLens API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files if present (single-image deployment)
FRONTEND_DIST = os.path.join(os.getcwd(), "frontend", "dist")
if os.path.isdir(FRONTEND_DIST):
    # Serve built assets under /assets (Vite outputs /assets)
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")
    # Serve other static files and enable SPA fallback for index.html
    app.mount("/static", StaticFiles(directory=FRONTEND_DIST), name="static")
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ThreatLens"}


@app.get("/")
def root():
    index_path = os.path.join("frontend", "dist", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {"status": "ok", "service": "ThreatLens", "note": "See /health and API endpoints"}


# SPA fallback: return index.html for GET requests without a file extension
@app.exception_handler(404)
async def spa_fallback(request: Request, exc):
    if request.method == "GET" and not os.path.splitext(request.url.path)[1]:
        index_path = os.path.join("frontend", "dist", "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path, media_type="text/html")
    raise exc


@app.get("/threats")
def get_threats(limit: int = Query(50, ge=1, le=500), severity_min: int = Query(1, ge=1, le=10)):
    return {"items": db.recent_threats(limit=limit, severity_min=severity_min)}


@app.get("/threats/export")
def export_threats_csv():
    threats = db.recent_threats(limit=500, severity_min=1)
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "timestamp", "source", "threat_type", "target", "severity", "ai_summary", "status"],
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(threats)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=threats_export.csv"},
    )


@app.get("/analytics/summary")
def analytics_summary():
    return db.analytics_summary()


@app.get("/analytics/clickhouse-benchmark")
def clickhouse_benchmark():
    queries = [
        {
            "name": "severity_histogram",
            "sql": "SELECT severity, count(), avg(triage_latency_ms) FROM threat_events GROUP BY severity ORDER BY severity",
        },
        {
            "name": "source_rollup_72h",
            "sql": "SELECT source, count(), quantile(0.95)(triage_latency_ms) FROM threat_events WHERE timestamp >= now() - INTERVAL 72 HOUR GROUP BY source ORDER BY count() DESC",
        },
        {
            "name": "top_10_critical_targets",
            "sql": "SELECT target, max(severity), count() FROM threat_events WHERE severity >= 9 GROUP BY target ORDER BY count() DESC LIMIT 10",
        },
    ]
    results = []
    for q in queries:
        start = time.perf_counter()
        result = db.client.query(q["sql"])
        execution_ms = round((time.perf_counter() - start) * 1000, 2)
        results.append({
            "name": q["name"],
            "sql": q["sql"],
            "execution_ms": execution_ms,
            "rows": len(result.result_rows),
        })
    return {"queries": results}


@app.get("/agent/runs")
def get_agent_runs(limit: int = Query(50, ge=1, le=200)):
    return {"items": db.agent_runs(limit=limit), "langfuse_host": settings.langfuse_project_url}


@app.get("/agent/status")
def agent_status():
    return {
        "running": agent._lock.locked(),
        "model": settings.groq_model,
        "interval_minutes": settings.agent_interval_minutes,
    }


@app.post("/agent/trigger")
async def trigger_agent():
    if agent._lock.locked():
        raise HTTPException(status_code=409, detail="Agent run already in progress")
    run = await agent.run_once()
    return run.model_dump(mode="json")


@app.post("/demo/reset")
def demo_reset():
    db.client.command("TRUNCATE TABLE IF EXISTS repo_vulns")
    db.client.command("TRUNCATE TABLE IF EXISTS repo_inventory")
    db.client.command("TRUNCATE TABLE IF EXISTS repo_scans")
    seed_repo_demo_data(db)
    return {"status": "reset", "message": "Demo data re-seeded"}


@app.get("/cves")
def get_cves(search: str = "", limit: int = Query(50, ge=1, le=200)):
    return {"items": db.search_cves(search=search, limit=limit)}


@app.post("/scan/github")
async def scan_github(payload: GitHubScanRequest):
    if not payload.username.strip():
        raise HTTPException(status_code=400, detail="username is required")
    return await repo_scanner.start_scan(payload.username)


@app.get("/scan/status/{scan_id}")
def scan_status(scan_id: str):
    status = repo_scanner.status.get(scan_id) or db.repo_scan_status(scan_id)
    if not status:
        raise HTTPException(status_code=404, detail="scan not found")
    return status


@app.get("/repos/{username}")
def repos(username: str):
    return {"items": db.repos_for_user(username), "analytics": db.repo_analytics(username)}


@app.get("/repos/{username}/{repo_name}/vulns")
def repo_vulns(username: str, repo_name: str):
    return {"items": db.repo_vulns(username, repo_name)}


@app.get("/feed/live")
def live_vuln_feed(limit: int = Query(100, ge=1, le=500)):
    return {"items": db.latest_repo_vulns(limit=limit)}


@app.websocket("/ws/feed")
async def websocket_feed(websocket: WebSocket):
    await hub.connect(websocket)
    with suppress(Exception):
        await websocket.send_json({"type": "hello", "message": "ThreatLens live feed connected"})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(websocket)


@app.websocket("/ws/scan/{scan_id}")
async def websocket_scan(scan_id: str, websocket: WebSocket):
    await scan_hub.connect(scan_id, websocket)
    with suppress(Exception):
        status = repo_scanner.status.get(scan_id) or db.repo_scan_status(scan_id)
        await websocket.send_json({"type": "hello", "scan_id": scan_id, "status": status})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        scan_hub.disconnect(scan_id, websocket)
