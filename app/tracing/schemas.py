from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SpanStatus = Literal["running", "ok", "error"]


class Span(BaseModel):
    id: str
    name: str
    parent_span_id: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    latency_ms: float | None = None
    input: Any = None
    output: Any = None
    model: str | None = None
    tokens: dict[str, Any] | None = None
    status: SpanStatus = "running"
    error: str | None = None


class Trace(BaseModel):
    trace_id: str
    started_at: datetime
    ended_at: datetime | None = None
    total_latency_ms: float | None = None
    spans: list[Span] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
