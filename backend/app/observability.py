import uuid
from contextlib import suppress
from typing import Any

from langfuse import Langfuse

from .config import Settings


class LangfuseTracer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: Langfuse | None = None
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            self.client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )

    def trace_id(self) -> str:
        return uuid.uuid4().hex

    def link(self, trace_id: str) -> str:
        base = self.settings.langfuse_project_url.rstrip("/") or self.settings.langfuse_host.rstrip("/")
        return f"{base}/trace/{trace_id}" if trace_id else base

    def create_trace(self, trace_id: str, name: str, metadata: dict[str, Any], tags: list[str]) -> Any:
        if not self.client:
            return None
        with suppress(Exception):
            return self.client.trace(id=trace_id, name=name, metadata=metadata, tags=tags)
        return None

    def generation(
        self,
        trace: Any,
        name: str,
        model: str,
        input_data: Any,
        output_data: Any,
        usage: dict[str, int],
        metadata: dict[str, Any],
        latency_ms: int,
    ) -> None:
        if not trace:
            return
        with suppress(Exception):
            generation = trace.generation(
                name=name,
                model=model,
                input=input_data,
                output=output_data,
                usage=usage,
                metadata={**metadata, "latency_ms": latency_ms, "generation_type": "threat-triage"},
            )
            generation.end()

    def score(self, trace: Any, name: str, value: float, comment: str) -> None:
        if not trace:
            return
        with suppress(Exception):
            trace.score(name=name, value=value, comment=comment)

    def flush(self) -> None:
        if self.client:
            with suppress(Exception):
                self.client.flush()
