from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from sentinelai import (
    ObservedResult,
    configure,
    observe,
    observe_execution,
    record_metadata,
    reset_configuration,
)
from sentinelai.contracts import ModelInfo, PromptReference
from sentinelai.execution_stream import (
    ExecutionCancelled,
    ExecutionCompleted,
    ExecutionEvent,
    ExecutionFailed,
    ExecutionStarted,
    InMemoryExecutionStream,
    TraceCompleted,
)


@pytest.fixture(autouse=True)
def _reset_sdk() -> None:
    reset_configuration()
    yield
    reset_configuration()


class _Plan(BaseModel):
    intent: str
    confidence: float


class _ExecutionResult(BaseModel):
    output: dict[str, Any]
    retrieval_result: dict[str, Any] | None = None


class _Capture:
    def __init__(self) -> None:
        self.events: list[ExecutionEvent] = []

    async def handle(self, event: ExecutionEvent) -> None:
        self.events.append(event)


def _configure(stream: InMemoryExecutionStream) -> _Capture:
    capture = _Capture()
    stream.subscribe(ExecutionEvent, capture)
    configure(
        publisher=stream,
        model_info=ModelInfo(provider="test", model_name="test-model"),
        prompt_catalog={
            "planner": PromptReference(
                prompt_id="planner",
                version="v1",
                name="Planner",
                hash="a" * 64,
            ),
            "executor.chat": PromptReference(
                prompt_id="executor.chat",
                version="v1",
                name="Chat",
                hash="b" * 64,
            ),
            "verifier": PromptReference(
                prompt_id="verifier",
                version="v1",
                name="Verifier",
                hash="c" * 64,
            ),
        },
    )
    return capture


@pytest.mark.asyncio
async def test_observe_execution_publishes_started_and_completed() -> None:
    stream = InMemoryExecutionStream()
    capture = _configure(stream)

    @observe_execution(execution_name="query", return_metadata=True)
    async def run(query: str) -> dict[str, str]:
        return {"answer": query}

    result = await run("hello")
    assert isinstance(result, ObservedResult)
    assert result.value == {"answer": "hello"}
    assert isinstance(result.metadata.execution_id, UUID)
    assert result.metadata.trace_id is not None
    assert result.metadata.execution_status == "completed"
    assert isinstance(capture.events[0], ExecutionStarted)
    assert isinstance(capture.events[-1], ExecutionCompleted)
    assert any(isinstance(event, TraceCompleted) for event in capture.events)


@pytest.mark.asyncio
async def test_observe_execution_marks_failure_and_preserves_exception() -> None:
    stream = InMemoryExecutionStream()
    capture = _configure(stream)

    @observe_execution(execution_name="query")
    async def run(query: str) -> str:
        raise RuntimeError(f"boom:{query}")

    with pytest.raises(RuntimeError, match="boom:hello"):
        await run("hello")

    assert isinstance(capture.events[0], ExecutionStarted)
    assert isinstance(capture.events[-1], ExecutionFailed)
    assert capture.events[-1].payload["snapshot"]["metadata"]["error_type"] == (
        "RuntimeError"
    )


@pytest.mark.asyncio
async def test_observe_execution_marks_cancellation() -> None:
    stream = InMemoryExecutionStream()
    capture = _configure(stream)

    @observe_execution(execution_name="query")
    async def run(query: str) -> str:
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await run("hello")

    assert isinstance(capture.events[-1], ExecutionCancelled)


@pytest.mark.asyncio
async def test_declarative_capture_and_prompt_selection() -> None:
    stream = InMemoryExecutionStream()
    capture = _configure(stream)

    @observe("planner", capture="plan", prompt_keys="planner")
    async def plan(user_query: str) -> _Plan:
        return _Plan(intent="chat", confidence=0.9)

    @observe(
        "executor",
        capture={"response": "output", "retrieval_result": "retrieval_result"},
        prompt_keys="executor.{intent}",
    )
    async def execute(plan_result: _Plan, user_query: str) -> _ExecutionResult:
        return _ExecutionResult(
            output={"response": f"answer:{user_query}"},
            retrieval_result=None,
        )

    @observe("verifier", capture="verification", prompt_keys="verifier")
    async def verify(answer: str) -> dict[str, Any]:
        return {"supported": True, "answer": answer}

    @observe_execution(
        execution_name="query",
        prompt_keys="planner",
        return_metadata=True,
    )
    async def run(query: str) -> str:
        planned = await plan(query)
        executed = await execute(planned, query)
        await verify(executed.output["response"])
        record_metadata(verification_status="ok")
        return executed.output["response"]

    result = await run("refund window")
    assert result.value == "answer:refund window"
    terminal = capture.events[-1]
    assert isinstance(terminal, ExecutionCompleted)
    snapshot = terminal.payload["snapshot"]
    assert snapshot["intent"] == "chat"
    assert snapshot["plan"]["intent"] == "chat"
    assert snapshot["response"]["response"] == "answer:refund window"
    assert snapshot["verification"]["supported"] is True
    assert "planner" in snapshot["prompt_references"]
    assert "executor.chat" in snapshot["prompt_references"]
    assert "verifier" in snapshot["prompt_references"]
    assert snapshot["metadata"]["verification_status"] == "ok"


@pytest.mark.asyncio
async def test_capture_is_noop_without_active_execution() -> None:
    @observe("planner", capture="plan")
    async def plan(user_query: str) -> _Plan:
        return _Plan(intent="chat", confidence=0.5)

    result = await plan("hello")
    assert result.intent == "chat"


@pytest.mark.asyncio
async def test_index_style_execution_omits_snapshot() -> None:
    stream = InMemoryExecutionStream()
    capture = _configure(stream)

    @observe_execution(
        execution_name="index_document",
        query=lambda content, filename=None, **_: f"index_document:{filename or 'untitled.txt'}",
        intent="document_index",
        include_snapshot=False,
        return_metadata=True,
    )
    async def index_document(content: str, filename: str | None = None) -> dict[str, str]:
        return {"content": content, "filename": filename or "untitled.txt"}

    result = await index_document("doc body", filename="policy.txt")
    assert result.metadata.intent == "document_index"
    terminal = capture.events[-1]
    assert isinstance(terminal, ExecutionCompleted)
    assert "snapshot" not in terminal.payload
    assert terminal.payload["query"] == "index_document:policy.txt"


@pytest.mark.asyncio
async def test_nested_executions_isolate_contextvars() -> None:
    stream = InMemoryExecutionStream()
    _configure(stream)
    seen: list[str] = []

    @observe_execution(execution_name="inner")
    async def inner(query: str) -> str:
        from sentinelai.execution.active import get_active_execution

        context = get_active_execution()
        assert context is not None
        seen.append(context.query)
        return query

    @observe_execution(execution_name="outer")
    async def outer(query: str) -> str:
        from sentinelai.execution.active import get_active_execution

        context = get_active_execution()
        assert context is not None
        assert context.query == query
        await inner(f"{query}-child")
        restored = get_active_execution()
        assert restored is not None
        assert restored.query == query
        return query

    await outer("parent")
    assert seen == ["parent-child"]


@pytest.mark.asyncio
async def test_publication_failure_does_not_mask_business_error() -> None:
    class BrokenPublisher:
        async def publish(self, event: ExecutionEvent) -> None:
            if event.event_type.startswith("execution.") and event.event_type != (
                "execution.started"
            ):
                raise RuntimeError("publish failed")
            return None

    configure(
        publisher=BrokenPublisher(),  # type: ignore[arg-type]
        model_info=ModelInfo(provider="test", model_name="test-model"),
    )

    @observe_execution(execution_name="query")
    async def run(query: str) -> str:
        raise ValueError("business failure")

    with pytest.raises(ValueError, match="business failure"):
        await run("hello")


@pytest.mark.asyncio
async def test_requires_configuration() -> None:
    @observe_execution(execution_name="query")
    async def run(query: str) -> str:
        return query

    with pytest.raises(RuntimeError, match="not configured"):
        await run("hello")


@pytest.mark.asyncio
async def test_concurrent_executions_keep_distinct_ids() -> None:
    stream = InMemoryExecutionStream()
    capture = _configure(stream)

    @observe_execution(execution_name="query", return_metadata=True)
    async def run(query: str) -> str:
        await asyncio.sleep(0.01)
        return query

    results = await asyncio.gather(run("one"), run("two"))
    ids = {result.metadata.execution_id for result in results}
    assert len(ids) == 2
    started = [event for event in capture.events if isinstance(event, ExecutionStarted)]
    assert len(started) == 2
    assert {event.execution_id for event in started} == ids
