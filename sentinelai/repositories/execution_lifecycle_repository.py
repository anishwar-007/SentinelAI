from __future__ import annotations

import builtins
from abc import ABC, abstractmethod
from uuid import UUID

from sentinelai.contracts.execution import ExecutionRecord

__all__ = [
    "ExecutionLifecycleRepository",
    "ExecutionRecord",
    "ExecutionRepository",
]


class ExecutionLifecycleRepository(ABC):
    """Mutable lifecycle ledger used while an execution is in flight."""

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


# Temporary alias for older imports during the SDK extraction.
ExecutionRepository = ExecutionLifecycleRepository
