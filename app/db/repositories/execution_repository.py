from __future__ import annotations

import builtins
from abc import ABC, abstractmethod
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


class ExecutionRepository(ABC):
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
