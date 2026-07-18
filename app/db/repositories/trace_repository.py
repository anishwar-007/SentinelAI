from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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


class TraceRepository(ABC):
    @abstractmethod
    async def create(
        self,
        trace: TraceRecord,
        spans: list[SpanRecord],
    ) -> TraceRecord:
        raise NotImplementedError

    @abstractmethod
    async def get(self, trace_id: UUID) -> TraceRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def list_spans(self, trace_id: UUID) -> list[SpanRecord]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, trace_id: UUID) -> None:
        raise NotImplementedError
