"""Platform-owned persistence projection DTOs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ExecutionRecord(BaseModel):
    id: UUID
    query: str
    intent: str | None
    status: str
    latency_ms: float | None
    created_at: datetime
    completed_at: datetime | None


class TraceRecord(BaseModel):
    trace_id: UUID
    execution_id: UUID
    status: str
    span_count: int
    latency_ms: float | None
    storage_path: str
    created_at: datetime


class SpanRecord(BaseModel):
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


__all__ = ["ExecutionRecord", "SpanRecord", "TraceRecord"]
