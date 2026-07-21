from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from sentinelai import (
    configure,
    execution,
    get_current_execution_id,
    get_current_trace_id,
    span,
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
from sentinelai.sdk.configure import reset_configuration


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


class _RunOutcome(BaseModel):
    intent: str
    result: dict[str, Any]
    verification: dict[str, Any] | None = None
    verification_status: str = "ok"


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
async def test_execution_publishes_started_and_completed() -> None:
    stream = InMemoryExecutionStream()
    capture = _configure(stream)

    @execution("query")
    async def run(query: str) -> dict[str, str]:
        return {"answer": query}

    result = await run("hello")
    assert result == {"answer": "hello"}
    assert isinstance(get_current_execution_id(), UUID)
    assert get_current_trace_id() is not None
    assert isinstance(capture.events[0], ExecutionStarted)
    assert isinstance(capture.events[-1], ExecutionCompleted)
    assert any(isinstance(event, TraceCompleted) for event in capture.events)


@pytest.mark.asyncio
async def test_execution_marks_failure_and_preserves_exception() -> None:
    stream = InMemoryExecutionStream()
    capture = _configure(stream)

    @execution("query")
    async def run(query: str) -> str:
        raise RuntimeError(f"boom:{query}")

    with pytest.raises(RuntimeError, match="boom:hello"):
        await run("hello")

    assert isinstance(capture.events[0], ExecutionStarted)
    assert isinstance(capture.events[-1], ExecutionFailed)
    assert capture.events[-1].metadata["error_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_execution_marks_cancellation() -> None:
    stream = InMemoryExecutionStream()
    capture = _configure(stream)

    @execution("query")
    async def run(query: str) -> str:
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await run("hello")

    assert isinstance(capture.events[-1], ExecutionCancelled)


@pytest.mark.asyncio
async def test_span_inference_and_prompt_selection() -> None:
    stream = InMemoryExecutionStream()
    capture = _configure(stream)

    @span("planner")
    async def plan(user_query: str) -> _Plan:
        return _Plan(intent="chat", confidence=0.9)

    @span("executor")
    async def execute(plan_result: _Plan, user_query: str) -> _ExecutionResult:
        return _ExecutionResult(
            output={"response": f"answer:{user_query}"},
            retrieval_result=None,
        )

    @span("verifier")
    async def verify(answer: str) -> dict[str, Any]:
        return {"supported": True, "answer": answer}

    @execution("query")
    async def run(query: str) -> _RunOutcome:
        planned = await plan(query)
        executed = await execute(planned, query)
        verification = await verify(executed.output["response"])
        return _RunOutcome(
            intent=planned.intent,
            result=executed.output,
            verification=verification,
            verification_status="ok",
        )

    result = await run("refund window")
    assert result.result["response"] == "answer:refund window"
    terminal = capture.events[-1]
    assert isinstance(terminal, ExecutionCompleted)
    assert "snapshot" not in terminal.payload
    assert terminal.payload["project_snapshot"] is True
    assert terminal.payload["intent"] == "chat"
    assert terminal.payload["plan"]["intent"] == "chat"
    assert terminal.payload["response"]["response"] == "answer:refund window"
    assert terminal.payload["verification"]["supported"] is True
    assert "planner" in terminal.payload["prompt_references"]
    assert "executor.chat" in terminal.payload["prompt_references"]
    assert "verifier" in terminal.payload["prompt_references"]
    assert terminal.metadata["verification_status"] == "ok"


@pytest.mark.asyncio
async def test_span_is_noop_without_active_execution() -> None:
    @span("planner")
    async def plan(user_query: str) -> _Plan:
        return _Plan(intent="chat", confidence=0.5)

    result = await plan("hello")
    assert result.intent == "chat"


@pytest.mark.asyncio
async def test_index_style_execution_omits_snapshot_projection() -> None:
    stream = InMemoryExecutionStream()
    capture = _configure(stream)

    @execution(
        "index_document",
        query=lambda content, filename=None, **_: (
            f"index_document:{filename or 'untitled.txt'}"
        ),
        intent="document_index",
        include_snapshot=False,
    )
    async def index_document(
        content: str,
        filename: str | None = None,
    ) -> dict[str, str]:
        return {"content": content, "filename": filename or "untitled.txt"}

    result = await index_document("doc body", filename="policy.txt")
    assert result["filename"] == "policy.txt"
    terminal = capture.events[-1]
    assert isinstance(terminal, ExecutionCompleted)
    assert "snapshot" not in terminal.payload or terminal.payload.get("snapshot") is None
    assert terminal.payload.get("project_snapshot") is False
    assert terminal.payload["query"] == "index_document:policy.txt"


@pytest.mark.asyncio
async def test_nested_executions_isolate_contextvars() -> None:
    stream = InMemoryExecutionStream()
    _configure(stream)
    seen: list[str] = []

    @execution("inner")
    async def inner(query: str) -> str:
        from sentinelai.execution.active import get_active_execution

        context = get_active_execution()
        assert context is not None
        seen.append(context.query)
        return query

    @execution("outer")
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

    @execution("query")
    async def run(query: str) -> str:
        raise ValueError("business failure")

    with pytest.raises(ValueError, match="business failure"):
        await run("hello")


@pytest.mark.asyncio
async def test_requires_configuration() -> None:
    @execution("query")
    async def run(query: str) -> str:
        return query

    with pytest.raises(RuntimeError, match="not configured"):
        await run("hello")


@pytest.mark.asyncio
async def test_concurrent_executions_keep_distinct_ids() -> None:
    stream = InMemoryExecutionStream()
    capture = _configure(stream)

    @execution("query")
    async def run(query: str) -> str:
        await asyncio.sleep(0.01)
        return query

    results = await asyncio.gather(run("one"), run("two"))
    assert set(results) == {"one", "two"}
    started = [event for event in capture.events if isinstance(event, ExecutionStarted)]
    assert len(started) == 2
    assert len({event.execution_id for event in started}) == 2
