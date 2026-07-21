"""Platform subscribers that persist execution lifecycle facts."""

from datetime import UTC, datetime
from typing import Any

from sentinelai.contracts import ExecutionSnapshot
from sentinelai.execution_stream import (
    ExecutionCancelled,
    ExecutionCompleted,
    ExecutionEvent,
    ExecutionFailed,
    ExecutionStarted,
)
from sentinelai_platform.projections import ExecutionRecord
from sentinelai_platform.repositories.execution import (
    ExecutionLifecycleRepository,
    ExecutionSnapshotRepository,
)


class ExecutionStartedSubscriber:
    def __init__(self, executions: ExecutionLifecycleRepository) -> None:
        self._executions = executions

    async def handle(self, event: ExecutionEvent) -> None:
        if not isinstance(event, ExecutionStarted):
            return
        payload = event.payload_dict()
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
        snapshots: ExecutionSnapshotRepository,
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
        snapshots: ExecutionSnapshotRepository,
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
        snapshots: ExecutionSnapshotRepository,
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
    snapshots: ExecutionSnapshotRepository,
) -> None:
    payload = event.payload_dict()
    raw_snapshot = payload.get("snapshot")
    if raw_snapshot is not None:
        await snapshots.save(ExecutionSnapshot.model_validate(raw_snapshot))
        return
    if payload.get("project_snapshot") is not True:
        return

    await snapshots.save(
        ExecutionSnapshot.model_validate(
            {
                "execution_id": event.execution_id,
                "query": payload.get("query"),
                "plan": payload.get("plan"),
                "retrieval_result": payload.get("retrieval_result"),
                "response": payload.get("response"),
                "verification": payload.get("verification"),
                "analysis": payload.get("analysis"),
                "trace_id": payload.get("trace_id"),
                "model_info": payload.get("model_info"),
                "prompt_references": payload.get("prompt_references", {}),
                "created_at": payload.get("created_at"),
                "metadata": event.metadata_dict(),
                "repository_version": payload.get("repository_version", "1.0"),
                "execution_status": payload.get("status"),
                "intent": payload.get("intent"),
            }
        )
    )


async def _update_execution(
    event: ExecutionEvent,
    executions: ExecutionLifecycleRepository,
    *,
    status: str,
) -> None:
    payload = event.payload_dict()
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
