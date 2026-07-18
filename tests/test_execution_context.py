from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from sentinelai import ExecutionContext, ExecutionSnapshot
from sentinelai.contracts import ModelInfo
from sentinelai.execution_stream import (
    ExecutionEvent,
    ExecutionFailed,
    InMemoryExecutionStream,
)


def test_execution_context_freezes_into_immutable_snapshot() -> None:
    context = ExecutionContext(
        query="What is the refund window?",
        model_info=ModelInfo(provider="test", model_name="test-model"),
        created_at=datetime.now(UTC),
    )
    context.set_stage("plan", {"intent": "rag_qa", "confidence": 0.9})
    context.set_stage("response", {"response": "30 days"})
    context.mark_completed()

    snapshot = context.to_snapshot()
    assert isinstance(snapshot, ExecutionSnapshot)
    assert snapshot.intent == "rag_qa"
    assert snapshot.plan == {"intent": "rag_qa", "confidence": 0.9}
    assert snapshot.response == {"response": "30 days"}
    assert snapshot.execution_status == "completed"

    with pytest.raises(ValidationError):
        snapshot.query = "mutated"  # type: ignore[misc]


def test_snapshot_requires_terminal_status() -> None:
    context = ExecutionContext(
        query="hello",
        model_info=ModelInfo(provider="test", model_name="test-model"),
    )
    with pytest.raises(ValueError, match="terminal"):
        context.to_snapshot()


@pytest.mark.asyncio
async def test_context_persist_publishes_terminal_event() -> None:
    published: list[ExecutionEvent] = []

    class CaptureSubscriber:
        async def handle(self, event: ExecutionEvent) -> None:
            published.append(event)

    stream = InMemoryExecutionStream()
    stream.subscribe(ExecutionEvent, CaptureSubscriber())
    context = ExecutionContext(
        execution_id=uuid4(),
        query="persist me",
        model_info=ModelInfo(provider="test", model_name="test-model"),
    )
    context.mark_failed(error=RuntimeError("boom"))
    snapshot, metrics = await context.persist(stream)
    assert isinstance(published[-1], ExecutionFailed)
    assert published[-1].payload["snapshot"]["execution_id"] == str(
        snapshot.execution_id
    )
    assert metrics.snapshot_size_bytes > 0
    assert metrics.publication_latency_ms >= 0
    assert snapshot.execution_status == "failed"
