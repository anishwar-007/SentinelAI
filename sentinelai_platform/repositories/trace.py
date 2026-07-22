from abc import ABC, abstractmethod
from uuid import UUID

from sentinelai_platform.projections import SpanRecord, TraceRecord


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
    async def find_by_execution_id(self, execution_id: UUID) -> TraceRecord | None:
        """Return the most recent trace record for an execution, if any."""
        raise NotImplementedError

    @abstractmethod
    async def list_spans(self, trace_id: UUID) -> list[SpanRecord]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, trace_id: UUID) -> None:
        raise NotImplementedError
