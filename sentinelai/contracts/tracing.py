from datetime import datetime
from typing import Any, Literal
from uuid import UUID

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


class TraceRecord(BaseModel):
    """Persistence DTO for one trace."""

    trace_id: UUID
    execution_id: UUID
    status: str
    span_count: int
    latency_ms: float | None
    storage_path: str
    created_at: datetime


class SpanRecord(BaseModel):
    """Persistence DTO for one stored span."""

    span_id: UUID
    trace_id: UUID
    parent_span_id: UUID | None
    span_type: str
    latency_ms: float | None
    model: str | None
    tokens_input: int | None
    tokens_output: int | None
    status: str
    error: str | None
    started_at: datetime | None
    ended_at: datetime | None
