from __future__ import annotations

from typing import Literal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from sentinelai.execution_stream import (
    AnalysisCompleted,
    ExecutionCancelled,
    ExecutionCompleted,
    ExecutionEvent,
    ExecutionFailed,
    ExecutionStarted,
    InMemoryExecutionStream,
    SpanCompleted,
    SpanStarted,
    TraceCompleted,
    TraceCreated,
    VerificationCompleted,
)


def test_execution_event_is_deeply_immutable() -> None:
    event = ExecutionStarted(
        execution_id=uuid4(),
        payload={"nested": {"items": [1, 2]}},
        metadata={"source": "test"},
    )

    with pytest.raises(ValidationError):
        event.event_type = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        event.payload["new"] = "value"  # type: ignore[index]
    with pytest.raises(TypeError):
        event.payload["nested"]["new"] = "value"  # type: ignore[index]
    assert event.payload["nested"]["items"] == (1, 2)
    assert event.model_dump(mode="json")["payload"] == {
        "nested": {"items": [1, 2]}
    }


@pytest.mark.parametrize(
    ("event_class", "event_type"),
    [
        (ExecutionStarted, "execution.started"),
        (ExecutionCompleted, "execution.completed"),
        (ExecutionFailed, "execution.failed"),
        (ExecutionCancelled, "execution.cancelled"),
        (TraceCreated, "trace.created"),
        (TraceCompleted, "trace.completed"),
        (SpanStarted, "span.started"),
        (SpanCompleted, "span.completed"),
        (VerificationCompleted, "verification.completed"),
        (AnalysisCompleted, "analysis.completed"),
    ],
)
def test_standard_execution_event_types(
    event_class: type[ExecutionEvent],
    event_type: str,
) -> None:
    assert event_class(execution_id=uuid4()).event_type == event_type


@pytest.mark.asyncio
async def test_stream_subscribes_unsubscribes_and_supports_new_events() -> None:
    received: list[str] = []

    class CaptureSubscriber:
        async def handle(self, event: ExecutionEvent) -> None:
            received.append(event.event_type)

    class PlannerCompleted(ExecutionEvent):
        event_type: Literal["planner.completed"] = "planner.completed"

    subscriber = CaptureSubscriber()
    stream = InMemoryExecutionStream()
    stream.subscribe(ExecutionEvent, subscriber)

    await stream.publish(ExecutionStarted(execution_id=uuid4()))
    await stream.publish(PlannerCompleted(execution_id=uuid4()))
    assert received == ["execution.started", "planner.completed"]

    stream.unsubscribe(ExecutionEvent, subscriber)
    await stream.publish(ExecutionStarted(execution_id=uuid4()))
    assert received == ["execution.started", "planner.completed"]


@pytest.mark.asyncio
async def test_stream_awaits_all_matching_subscribers() -> None:
    completed: list[str] = []

    class FirstSubscriber:
        async def handle(self, event: ExecutionEvent) -> None:
            completed.append(f"first:{event.event_type}")

    class SecondSubscriber:
        async def handle(self, event: ExecutionEvent) -> None:
            completed.append(f"second:{event.event_type}")

    stream = InMemoryExecutionStream()
    stream.subscribe(ExecutionStarted, FirstSubscriber())
    stream.subscribe(ExecutionStarted, SecondSubscriber())
    await stream.publish(ExecutionStarted(execution_id=uuid4()))

    assert set(completed) == {
        "first:execution.started",
        "second:execution.started",
    }


@pytest.mark.asyncio
async def test_stream_finishes_fanout_before_propagating_failure() -> None:
    completed: list[str] = []

    class FailingSubscriber:
        async def handle(self, event: ExecutionEvent) -> None:
            completed.append("failed")
            raise RuntimeError(event.event_type)

    class SuccessfulSubscriber:
        async def handle(self, event: ExecutionEvent) -> None:
            completed.append("succeeded")

    stream = InMemoryExecutionStream()
    stream.subscribe(ExecutionStarted, FailingSubscriber())
    stream.subscribe(ExecutionStarted, SuccessfulSubscriber())

    with pytest.raises(RuntimeError, match="execution.started"):
        await stream.publish(ExecutionStarted(execution_id=uuid4()))
    assert set(completed) == {"failed", "succeeded"}
