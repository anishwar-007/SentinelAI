from __future__ import annotations

import builtins
from abc import ABC, abstractmethod
from uuid import UUID

from sentinelai.contracts import ExecutionSnapshot, ExecutionSummary


class ExecutionAlreadyExistsError(RuntimeError):
    pass


# Backward-compatible alias used by earlier milestones.
ExecutionSnapshotAlreadyExistsError = ExecutionAlreadyExistsError


class ExecutionRepository(ABC):
    """Append-only persistence port for immutable execution history."""

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
    ) -> builtins.list[ExecutionSummary]:
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


# Compatibility alias for the previous naming.
ExecutionSnapshotRepository = ExecutionRepository
