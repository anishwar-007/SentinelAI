from __future__ import annotations

import builtins
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sentinelai_platform.persistence.postgres.models_execution import ExecutionModel
from sentinelai_platform.projections import ExecutionRecord
from sentinelai_platform.repositories.execution import ExecutionLifecycleRepository


class PostgresExecutionLifecycleRepository(ExecutionLifecycleRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, execution: ExecutionRecord) -> ExecutionRecord:
        async with self._session_factory() as session:
            row = ExecutionModel(
                id=execution.id,
                query=execution.query,
                intent=execution.intent,
                status=execution.status,
                latency_ms=execution.latency_ms,
                created_at=execution.created_at,
                completed_at=execution.completed_at,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _to_execution_record(row)

    async def update(self, execution: ExecutionRecord) -> ExecutionRecord:
        async with self._session_factory() as session:
            row = await session.get(ExecutionModel, execution.id)
            if row is None:
                raise LookupError(f"Execution not found: {execution.id}")
            row.query = execution.query
            row.intent = execution.intent
            row.status = execution.status
            row.latency_ms = execution.latency_ms
            row.completed_at = execution.completed_at or datetime.now(UTC)
            await session.commit()
            await session.refresh(row)
            return _to_execution_record(row)

    async def get(self, execution_id: UUID) -> ExecutionRecord | None:
        async with self._session_factory() as session:
            row = await session.get(ExecutionModel, execution_id)
            if row is None:
                return None
            return _to_execution_record(row)

    async def delete(self, execution_id: UUID) -> None:
        async with self._session_factory() as session:
            row = await session.get(ExecutionModel, execution_id)
            if row is None:
                raise LookupError(f"Execution not found: {execution_id}")
            await session.delete(row)
            await session.commit()

    async def list(self, *, limit: int = 100) -> builtins.list[ExecutionRecord]:
        async with self._session_factory() as session:
            result = await session.scalars(
                select(ExecutionModel)
                .order_by(ExecutionModel.created_at.desc())
                .limit(limit)
            )
            return [_to_execution_record(row) for row in result.all()]


def _to_execution_record(row: ExecutionModel) -> ExecutionRecord:
    return ExecutionRecord(
        id=row.id,
        query=row.query,
        intent=row.intent,
        status=row.status,
        latency_ms=row.latency_ms,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )
