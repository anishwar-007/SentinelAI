from __future__ import annotations

import builtins
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from sentinelai.contracts import ExecutionSnapshot, ExecutionSummary
from sentinelai_platform.projections import ExecutionRecord


class ExecutionSnapshotAlreadyExistsError(RuntimeError):
    pass


class ExecutionSnapshotRepository(ABC):
    """Append-only repository for the ExecutionSnapshot projection."""

    @abstractmethod
    async def save(self, snapshot: ExecutionSnapshot) -> ExecutionSnapshot:
        raise NotImplementedError

    @abstractmethod
    async def load(self, execution_id: UUID) -> ExecutionSnapshot | None:
        raise NotImplementedError

    @abstractmethod
    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
        execution_name: str | None = None,
        model: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> builtins.list[ExecutionSummary]:
        raise NotImplementedError

    @abstractmethod
    async def count(
        self,
        *,
        status: str | None = None,
        execution_name: str | None = None,
        model: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    async def find_by_trace(self, trace_id: UUID) -> ExecutionSnapshot | None:
        raise NotImplementedError

    @abstractmethod
    async def find_by_query(
        self,
        query: str,
        *,
        limit: int = 100,
    ) -> builtins.list[ExecutionSummary]:
        raise NotImplementedError


class ExecutionLifecycleRepository(ABC):
    """Mutable Platform projection of execution lifecycle events."""

    @abstractmethod
    async def create(self, execution: ExecutionRecord) -> ExecutionRecord:
        raise NotImplementedError

    @abstractmethod
    async def update(self, execution: ExecutionRecord) -> ExecutionRecord:
        raise NotImplementedError

    @abstractmethod
    async def get(self, execution_id: UUID) -> ExecutionRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, execution_id: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list(self, *, limit: int = 100) -> builtins.list[ExecutionRecord]:
        raise NotImplementedError
