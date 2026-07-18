from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from sentinelai import ExecutionContext
from sentinelai.contracts import (
    ExecutionRecord,
    ExecutionSnapshot,
    ExecutionSummary,
    ModelInfo,
    Trace,
)
from sentinelai.execution_stream import (
    ExecutionEvent,
    InMemoryExecutionStream,
)
from sentinelai_platform.event_subscribers import register_persistence_subscribers


class MemoryLifecycleRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, ExecutionRecord] = {}

    async def create(self, execution: ExecutionRecord) -> ExecutionRecord:
        self.rows[execution.id] = execution
        return execution

    async def update(self, execution: ExecutionRecord) -> ExecutionRecord:
        self.rows[execution.id] = execution
        return execution

    async def get(self, execution_id: UUID) -> ExecutionRecord | None:
        return self.rows.get(execution_id)

    async def delete(self, execution_id: UUID) -> None:
        self.rows.pop(execution_id, None)

    async def list(self, *, limit: int = 100) -> list[ExecutionRecord]:
        return list(self.rows.values())[:limit]


class MemorySnapshotRepository:
    def __init__(self) -> None:
        self.saved: list[ExecutionSnapshot] = []

    async def save(self, snapshot: ExecutionSnapshot) -> ExecutionSnapshot:
        self.saved.append(snapshot)
        return snapshot

    async def load(self, execution_id: UUID) -> ExecutionSnapshot | None:
        return next(
            (
                snapshot
                for snapshot in self.saved
                if snapshot.execution_id == execution_id
            ),
            None,
        )

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExecutionSummary]:
        return []

    async def find_by_trace(self, trace_id: UUID) -> ExecutionSnapshot | None:
        return next(
            (snapshot for snapshot in self.saved if snapshot.trace_id == trace_id),
            None,
        )

    async def find_by_query(
        self,
        query: str,
        *,
        limit: int = 100,
    ) -> list[ExecutionSummary]:
        return []


class MemoryTracePersister:
    def __init__(self) -> None:
        self.persisted: list[tuple[Trace, UUID]] = []

    async def persist(self, trace: Trace, execution_id: UUID) -> str:
        self.persisted.append((trace, execution_id))
        return f"traces/{trace.trace_id}.json"


@pytest.mark.asyncio
async def test_platform_projects_execution_stream_into_existing_stores() -> None:
    lifecycle = MemoryLifecycleRepository()
    snapshots = MemorySnapshotRepository()
    traces = MemoryTracePersister()
    event_types: list[str] = []

    class CaptureSubscriber:
        async def handle(self, event: ExecutionEvent) -> None:
            event_types.append(event.event_type)

    stream = InMemoryExecutionStream()
    register_persistence_subscribers(
        stream,
        executions=lifecycle,  # type: ignore[arg-type]
        snapshots=snapshots,  # type: ignore[arg-type]
        trace_persister=traces,  # type: ignore[arg-type]
    )
    stream.subscribe(ExecutionEvent, CaptureSubscriber())

    context = ExecutionContext(
        execution_id=uuid4(),
        query="observe this",
        model_info=ModelInfo(provider="test", model_name="model"),
    )
    context.mark_running()
    await context.publish_started(stream)
    context.set_stage("verification", {"verdict": "approved"})
    context.set_stage("analysis", {"summary": "healthy"})
    context.attach_trace(
        Trace(
            trace_id=str(uuid4()),
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
        )
    )
    context.mark_completed()
    await context.publish_terminal(stream)

    assert lifecycle.rows[context.execution_id].status == "completed"
    assert snapshots.saved[0].execution_id == context.execution_id
    assert traces.persisted[0][1] == context.execution_id
    assert event_types == [
        "execution.started",
        "trace.created",
        "trace.completed",
        "verification.completed",
        "analysis.completed",
        "execution.completed",
    ]
