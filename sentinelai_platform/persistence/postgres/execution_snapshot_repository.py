from __future__ import annotations

import builtins
import hashlib
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from sentinelai.contracts import (
    ExecutionSnapshot,
    ExecutionSummary,
    TerminalExecutionStatus,
)
from sentinelai_platform.persistence.postgres.models_execution import ExecutionModel
from sentinelai_platform.persistence.postgres.models_snapshot import ExecutionSnapshotModel
from sentinelai_platform.repositories.execution import (
    ExecutionSnapshotAlreadyExistsError,
    ExecutionSnapshotRepository,
)


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
        status: str | None = None,
        execution_name: str | None = None,
        model: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> builtins.list[ExecutionSummary]:
        async with self._session_factory() as session:
            stmt = _filtered_list_statement(
                status=status,
                execution_name=execution_name,
                model=model,
                from_time=from_time,
                to_time=to_time,
            )
            result = await session.execute(
                stmt.order_by(ExecutionSnapshotModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return [
                _to_summary(snapshot_row, latency_ms=latency, completed_at=completed)
                for snapshot_row, latency, completed in result.all()
            ]

    async def count(
        self,
        *,
        status: str | None = None,
        execution_name: str | None = None,
        model: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> int:
        async with self._session_factory() as session:
            stmt = select(func.count()).select_from(ExecutionSnapshotModel)
            stmt = _apply_filters(
                stmt,
                status=status,
                execution_name=execution_name,
                model=model,
                from_time=from_time,
                to_time=to_time,
            )
            total = await session.scalar(stmt)
            return int(total or 0)

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
            lifecycle = aliased(ExecutionModel)
            result = await session.execute(
                select(
                    ExecutionSnapshotModel,
                    lifecycle.latency_ms,
                    lifecycle.completed_at,
                )
                .outerjoin(
                    lifecycle,
                    lifecycle.id == ExecutionSnapshotModel.execution_id,
                )
                .where(
                    ExecutionSnapshotModel.query_hash == _query_hash(query),
                    ExecutionSnapshotModel.query == query,
                )
                .order_by(ExecutionSnapshotModel.created_at.desc())
                .limit(limit)
            )
            return [
                _to_summary(snapshot_row, latency_ms=latency, completed_at=completed)
                for snapshot_row, latency, completed in result.all()
            ]


def _filtered_list_statement(
    *,
    status: str | None,
    execution_name: str | None,
    model: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> Select[Any]:
    lifecycle = aliased(ExecutionModel)
    stmt: Select[Any] = select(
        ExecutionSnapshotModel,
        lifecycle.latency_ms,
        lifecycle.completed_at,
    ).outerjoin(
        lifecycle,
        lifecycle.id == ExecutionSnapshotModel.execution_id,
    )
    return _apply_filters(
        stmt,
        status=status,
        execution_name=execution_name,
        model=model,
        from_time=from_time,
        to_time=to_time,
    )


def _apply_filters(
    stmt: Select[Any],
    *,
    status: str | None,
    execution_name: str | None,
    model: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> Select[Any]:
    if status is not None:
        stmt = stmt.where(ExecutionSnapshotModel.execution_status == status)
    if model is not None:
        stmt = stmt.where(ExecutionSnapshotModel.model_name == model)
    if from_time is not None:
        stmt = stmt.where(ExecutionSnapshotModel.created_at >= from_time)
    if to_time is not None:
        stmt = stmt.where(ExecutionSnapshotModel.created_at <= to_time)
    if execution_name is not None:
        # Prefer JSONB path over loading full snapshots for list filtering.
        name_path = ExecutionSnapshotModel.snapshot_data["metadata"][
            "execution_name"
        ].as_string()
        stmt = stmt.where(name_path == execution_name)
    return stmt


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def _to_snapshot(row: ExecutionSnapshotModel) -> ExecutionSnapshot:
    return ExecutionSnapshot.model_validate(row.snapshot_data)


def _to_summary(
    row: ExecutionSnapshotModel,
    *,
    latency_ms: float | None = None,
    completed_at: datetime | None = None,
) -> ExecutionSummary:
    metadata = row.snapshot_data.get("metadata") if isinstance(row.snapshot_data, dict) else None
    execution_name: str | None = None
    if isinstance(metadata, dict):
        raw_name = metadata.get("execution_name")
        execution_name = raw_name if isinstance(raw_name, str) else None
    return ExecutionSummary(
        execution_id=row.execution_id,
        query=row.query,
        intent=row.intent,
        trace_id=row.trace_id,
        model_name=row.model_name,
        execution_status=cast(TerminalExecutionStatus, row.execution_status),
        repository_version=row.repository_version,
        created_at=row.created_at,
        execution_name=execution_name,
        latency_ms=latency_ms,
        completed_at=completed_at,
    )
