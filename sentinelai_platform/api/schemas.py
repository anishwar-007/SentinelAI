"""Platform HTTP request/response contracts for Dashboard V1 read APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from sentinelai.contracts import ExecutionSummary, TerminalExecutionStatus

TerminalStatusFilter = Literal["completed", "failed", "cancelled"]


class ExecutionListItem(BaseModel):
    """Execution Explorer row (no full snapshot)."""

    model_config = ConfigDict(frozen=True)

    execution_id: UUID
    execution_name: str | None = None
    status: TerminalExecutionStatus
    intent: str | None = None
    model: str
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: float | None = None
    trace_id: UUID | None = None
    query: str
    repository_version: str

    @classmethod
    def from_summary(cls, summary: ExecutionSummary) -> Self:
        return cls(
            execution_id=summary.execution_id,
            execution_name=summary.execution_name,
            status=summary.execution_status,
            intent=summary.intent,
            model=summary.model_name,
            started_at=summary.created_at,
            completed_at=summary.completed_at,
            latency_ms=summary.latency_ms,
            trace_id=summary.trace_id,
            query=summary.query,
            repository_version=summary.repository_version,
        )


class PaginatedExecutions(BaseModel):
    """Offset-paginated execution list."""

    model_config = ConfigDict(frozen=True)

    items: list[ExecutionListItem]
    limit: int
    offset: int
    total: int | None = None
    has_more: bool


class SpanView(BaseModel):
    """Span payload for Trace Timeline / Span Inspector."""

    model_config = ConfigDict(frozen=True)

    span_id: str
    parent_span_id: str | None = None
    name: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    latency_ms: float | None = None
    input: Any = None
    output: Any = None
    model: str | None = None
    tokens: dict[str, Any] | None = None
    error: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ExecutionTraceView(BaseModel):
    """Full trace for one execution, preserving parent/child span links."""

    model_config = ConfigDict(frozen=True)

    trace_id: str
    execution_id: UUID
    started_at: datetime
    completed_at: datetime | None = None
    total_latency_ms: float | None = None
    spans: list[SpanView] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ErrorBody(BaseModel):
    detail: str
