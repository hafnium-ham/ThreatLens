from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Decision = Literal["IGNORE", "MONITOR", "ALERT"]


class RawThreat(BaseModel):
    id: str
    timestamp: datetime
    source: str
    target: str
    raw_data: dict[str, Any]


class TriageResult(BaseModel):
    severity: int = Field(ge=1, le=10)
    threat_type: str
    summary: str
    decision: Decision
    reasoning: str
    latency_ms: int
    trace_id: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ThreatEvent(BaseModel):
    id: str
    timestamp: datetime
    source: str
    threat_type: str
    target: str
    severity: int
    raw_data: dict[str, Any]
    ai_summary: str
    status: Decision
    triage_latency_ms: int = 0
    langfuse_trace_id: str = ""


class AgentRun(BaseModel):
    id: str
    timestamp: datetime
    duration_ms: int
    threats_found: int
    model_used: str
    langfuse_trace_id: str
    status: str = "success"
    severity_breakdown: dict[str, int] = Field(default_factory=dict)


class CveIntel(BaseModel):
    cve_id: str
    published_date: datetime
    cvss_score: float
    description: str
    affected_products: list[str]
    ai_triage_notes: str
