"""Platform subscribers that persist execution lifecycle facts."""

from datetime import UTC, datetime
from typing import Any

from sentinelai.contracts import ExecutionRecord, ExecutionSnapshot
from sentinelai.execution_stream import (
    ExecutionCancelled,
    ExecutionCompleted,
    ExecutionEvent,
    ExecutionFailed,
    ExecutionStarted,
)
from sentinelai.repositories.execution_lifecycle_repository import (
    ExecutionLifecycleRepository,
)
from sentinelai.repositories.execution_repository import ExecutionRepository


class ExecutionStartedSubscriber:
    def __init__(self, executions: ExecutionLifecycleRepository) -> None:
        self._executions = executions

    async def handle(self, event: ExecutionEvent) -> None:
        if not isinstance(event, ExecutionStarted):
            return
        payload = event.payload
        await self._executions.create(
            ExecutionRecord(
                id=event.execution_id,
                query=_required_string(payload, "query"),
                intent=_optional_string(payload.get("intent")),
                status="running",
                latency_ms=None,
                created_at=_datetime_value(payload.get("created_at"), event.occurred_at),
                completed_at=None,
            )
        )


class ExecutionCompletedSubscriber:
    def __init__(
        self,
        executions: ExecutionLifecycleRepository,
        snapshots: ExecutionRepository,
    ) -> None:
        self._executions = executions
        self._snapshots = snapshots

    async def handle(self, event: ExecutionEvent) -> None:
        if not isinstance(event, ExecutionCompleted):
            return
        try:
            await _save_snapshot_if_present(event, self._snapshots)
        except Exception:
            await _update_execution(event, self._executions, status="failed")
            raise
        await _update_execution(event, self._executions, status="completed")


class ExecutionFailedSubscriber:
    def __init__(
        self,
        executions: ExecutionLifecycleRepository,
        snapshots: ExecutionRepository,
    ) -> None:
        self._executions = executions
        self._snapshots = snapshots

    async def handle(self, event: ExecutionEvent) -> None:
        if not isinstance(event, ExecutionFailed):
            return
        try:
            await _save_snapshot_if_present(event, self._snapshots)
        finally:
            await _update_execution(event, self._executions, status="failed")


class ExecutionCancelledSubscriber:
    def __init__(
        self,
        executions: ExecutionLifecycleRepository,
        snapshots: ExecutionRepository,
    ) -> None:
        self._executions = executions
        self._snapshots = snapshots

    async def handle(self, event: ExecutionEvent) -> None:
        if not isinstance(event, ExecutionCancelled):
            return
        try:
            await _save_snapshot_if_present(event, self._snapshots)
        finally:
            await _update_execution(event, self._executions, status="cancelled")


async def _save_snapshot_if_present(
    event: ExecutionEvent,
    snapshots: ExecutionRepository,
) -> None:
    raw_snapshot = event.payload.get("snapshot")
    if raw_snapshot is None:
        return
    await snapshots.save(ExecutionSnapshot.model_validate(raw_snapshot))


async def _update_execution(
    event: ExecutionEvent,
    executions: ExecutionLifecycleRepository,
    *,
    status: str,
) -> None:
    payload = event.payload
    await executions.update(
        ExecutionRecord(
            id=event.execution_id,
            query=_required_string(payload, "query"),
            intent=_optional_string(payload.get("intent")),
            status=status,
            latency_ms=_optional_float(payload.get("latency_ms")),
            created_at=_datetime_value(payload.get("created_at"), event.occurred_at),
            completed_at=_datetime_value(
                payload.get("completed_at"),
                datetime.now(UTC),
            ),
        )
    )


def _required_string(payload: dict[str, Any] | Any, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Execution event payload requires string field: {key}")
    return value


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _datetime_value(value: Any, default: datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return default
