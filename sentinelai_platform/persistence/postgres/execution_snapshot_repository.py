from __future__ import annotations

import builtins
import hashlib
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sentinelai.contracts import (
    ExecutionSnapshot,
    ExecutionSummary,
    TerminalExecutionStatus,
)
from sentinelai.repositories.execution_repository import (
    ExecutionSnapshotAlreadyExistsError,
    ExecutionSnapshotRepository,
)
from sentinelai_platform.persistence.postgres.models_snapshot import ExecutionSnapshotModel


class PostgresExecutionSnapshotRepository(ExecutionSnapshotRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, snapshot: ExecutionSnapshot) -> ExecutionSnapshot:
        row = ExecutionSnapshotModel(
            execution_id=snapshot.execution_id,
            trace_id=snapshot.trace_id,
            query=snapshot.query,
            query_hash=_query_hash(snapshot.query),
            execution_status=snapshot.execution_status,
            repository_version=snapshot.repository_version,
            model_name=snapshot.model_info.model_name,
            intent=snapshot.intent
            or (
                snapshot.plan.get("intent")
                if isinstance(snapshot.plan, dict)
                else None
            ),
            created_at=snapshot.created_at,
            snapshot_data=snapshot.model_dump(mode="json"),
        )
        async with self._session_factory() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                if getattr(exc.orig, "sqlstate", None) == "23505":
                    raise ExecutionSnapshotAlreadyExistsError(
                        f"Execution snapshot already exists: {snapshot.execution_id}"
                    ) from exc
                raise
        return snapshot

    async def load(self, execution_id: UUID) -> ExecutionSnapshot | None:
        async with self._session_factory() as session:
            row = await session.get(ExecutionSnapshotModel, execution_id)
            return _to_snapshot(row) if row is not None else None

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> builtins.list[ExecutionSummary]:
        async with self._session_factory() as session:
            result = await session.scalars(
                select(ExecutionSnapshotModel)
                .order_by(ExecutionSnapshotModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return [_to_summary(row) for row in result.all()]

    async def find_by_trace(self, trace_id: UUID) -> ExecutionSnapshot | None:
        async with self._session_factory() as session:
            result = await session.scalars(
                select(ExecutionSnapshotModel).where(
                    ExecutionSnapshotModel.trace_id == trace_id
                )
            )
            row = result.first()
            return _to_snapshot(row) if row is not None else None

    async def find_by_query(
        self,
        query: str,
        *,
        limit: int = 100,
    ) -> builtins.list[ExecutionSummary]:
        async with self._session_factory() as session:
            result = await session.scalars(
                select(ExecutionSnapshotModel)
                .where(
                    ExecutionSnapshotModel.query_hash == _query_hash(query),
                    ExecutionSnapshotModel.query == query,
                )
                .order_by(ExecutionSnapshotModel.created_at.desc())
                .limit(limit)
            )
            return [_to_summary(row) for row in result.all()]


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def _to_snapshot(row: ExecutionSnapshotModel) -> ExecutionSnapshot:
    return ExecutionSnapshot.model_validate(row.snapshot_data)


def _to_summary(row: ExecutionSnapshotModel) -> ExecutionSummary:
    return ExecutionSummary(
        execution_id=row.execution_id,
        query=row.query,
        intent=row.intent,
        trace_id=row.trace_id,
        model_name=row.model_name,
        execution_status=cast(TerminalExecutionStatus, row.execution_status),
        repository_version=row.repository_version,
        created_at=row.created_at,
    )
