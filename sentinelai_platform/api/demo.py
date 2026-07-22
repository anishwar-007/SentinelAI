"""Public demo routes. Sandbox by default; runtimes may inject a real runner."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from sentinelai.contracts import ExecutionSnapshot, ModelInfo, Trace
from sentinelai.contracts.tracing import Span
from sentinelai_platform.api.schemas import ExecutionTraceView
from sentinelai_platform.api.trace_views import project_trace_view

router = APIRouter(prefix="/api/v1/demo", tags=["public-demo"])

_RATE_LIMIT = 5
_RATE_WINDOW = timedelta(hours=1)
_SANDBOX_METADATA = {"environment": "sandbox", "source": "public_demo"}
_DEMO_QUERY_RUNNER_ATTR = "demo_query_runner"


class DemoQueryRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: Literal["chat", "rag", "invoice"]
    input: str = Field(max_length=500)

    @field_validator("input")
    @classmethod
    def input_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("input must not be blank")
        return stripped


class DemoQueryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_id: UUID
    answer: str
    status: Literal["completed"]
    latency_ms: float
    mode: Literal["chat", "rag", "invoice"]


class DemoQueryResult(BaseModel):
    """Result produced by an injected runtime demo runner."""

    model_config = ConfigDict(frozen=True)

    execution_id: UUID
    answer: str
    latency_ms: float
    mode: Literal["chat", "rag", "invoice"]
    snapshot: ExecutionSnapshot
    trace: Trace


DemoQueryRunner = Callable[[DemoQueryRequest], Awaitable[DemoQueryResult]]


@router.post("/query", response_model=DemoQueryResponse)
async def run_demo_query(
    payload: DemoQueryRequest,
    request: Request,
) -> DemoQueryResponse:
    """Run a demo query via injected runner, or the deterministic sandbox."""
    _enforce_rate_limit(request)
    runner = _demo_query_runner(request)
    if runner is not None:
        result = await runner(payload)
        _demo_executions(request)[result.execution_id] = {
            "snapshot": result.snapshot,
            "trace": result.trace,
        }
        return DemoQueryResponse(
            execution_id=result.execution_id,
            answer=result.answer,
            status="completed",
            latency_ms=result.latency_ms,
            mode=result.mode,
        )

    return _run_sandbox_demo(payload, request)


@router.get("/executions/{execution_id}", response_model=ExecutionSnapshot)
async def get_demo_execution(execution_id: UUID, request: Request) -> ExecutionSnapshot:
    record = _sandbox_record(request, execution_id)
    return record["snapshot"]


@router.get("/executions/{execution_id}/trace", response_model=ExecutionTraceView)
async def get_demo_execution_trace(
    execution_id: UUID,
    request: Request,
) -> ExecutionTraceView:
    record = _sandbox_record(request, execution_id)
    trace = record["trace"]
    return project_trace_view(trace, execution_id=execution_id)


def _demo_query_runner(request: Request) -> DemoQueryRunner | None:
    runner = getattr(request.app.state, _DEMO_QUERY_RUNNER_ATTR, None)
    return runner if callable(runner) else None


def _run_sandbox_demo(payload: DemoQueryRequest, request: Request) -> DemoQueryResponse:
    started_at = datetime.now(UTC)
    timer = perf_counter()
    execution_id = uuid4()
    trace_id = uuid4()
    answer = _demo_answer(payload.mode, payload.input)
    latency_ms = round((perf_counter() - timer) * 1000, 3)
    completed_at = datetime.now(UTC)

    snapshot = ExecutionSnapshot(
        execution_id=execution_id,
        query=payload.input,
        response={"answer": answer},
        trace_id=trace_id,
        model_info=ModelInfo(provider="sentinelai-demo", model_name="sandbox-simulator"),
        created_at=started_at,
        metadata={**_SANDBOX_METADATA, "execution_name": "public_demo"},
        execution_status="completed",
        intent=payload.mode,
    )
    trace = _build_trace(
        trace_id=trace_id,
        input_text=payload.input,
        answer=answer,
        started_at=started_at,
        completed_at=completed_at,
        latency_ms=latency_ms,
    )
    _demo_executions(request)[execution_id] = {"snapshot": snapshot, "trace": trace}

    return DemoQueryResponse(
        execution_id=execution_id,
        answer=answer,
        status="completed",
        latency_ms=latency_ms,
        mode=payload.mode,
    )


def _enforce_rate_limit(request: Request) -> None:
    now = datetime.now(UTC)
    client_ip = request.client.host if request.client is not None else "unknown"
    limits: dict[str, list[datetime]] = getattr(request.app.state, "demo_rate_limits", None)
    if limits is None:
        limits = defaultdict(list)
        request.app.state.demo_rate_limits = limits

    recent = [
        timestamp
        for timestamp in limits.get(client_ip, [])
        if now - timestamp < _RATE_WINDOW
    ]
    if len(recent) >= _RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demo rate limit exceeded. Try again later.",
        )
    recent.append(now)
    limits[client_ip] = recent


def _demo_executions(request: Request) -> dict[UUID, dict[str, Any]]:
    store: dict[UUID, dict[str, Any]] | None = getattr(
        request.app.state, "demo_executions", None
    )
    if store is None:
        store = {}
        request.app.state.demo_executions = store
    return store


def _sandbox_record(request: Request, execution_id: UUID) -> dict[str, Any]:
    record = _demo_executions(request).get(execution_id)
    snapshot = record.get("snapshot") if record is not None else None
    metadata = getattr(snapshot, "metadata", {})
    if not isinstance(metadata, dict) or metadata.get("environment") != "sandbox":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo execution not found.",
        )
    return record


def _build_trace(
    *,
    trace_id: UUID,
    input_text: str,
    answer: str,
    started_at: datetime,
    completed_at: datetime,
    latency_ms: float,
) -> Trace:
    root_id = str(uuid4())
    planner_id = str(uuid4())
    executor_id = str(uuid4())
    llm_id = str(uuid4())
    planner_end = started_at + timedelta(milliseconds=latency_ms * 0.2)
    executor_end = started_at + timedelta(milliseconds=latency_ms * 0.6)

    return Trace(
        trace_id=str(trace_id),
        started_at=started_at,
        ended_at=completed_at,
        total_latency_ms=latency_ms,
        metadata=dict(_SANDBOX_METADATA),
        spans=[
            Span(
                id=root_id,
                name="demo.query",
                start_time=started_at,
                end_time=completed_at,
                latency_ms=latency_ms,
                status="ok",
                input={"input": input_text},
                output={"answer": answer},
            ),
            Span(
                id=planner_id,
                parent_span_id=root_id,
                name="planner",
                start_time=started_at,
                end_time=planner_end,
                latency_ms=round(latency_ms * 0.2, 3),
                status="ok",
            ),
            Span(
                id=executor_id,
                parent_span_id=root_id,
                name="executor",
                start_time=planner_end,
                end_time=executor_end,
                latency_ms=round(latency_ms * 0.4, 3),
                status="ok",
            ),
            Span(
                id=llm_id,
                parent_span_id=executor_id,
                name="llm",
                start_time=executor_end,
                end_time=completed_at,
                latency_ms=round(latency_ms * 0.4, 3),
                model="sandbox-simulator",
                tokens={"prompt_tokens": len(input_text.split()), "completion_tokens": 16},
                status="ok",
                output={"answer": answer},
            ),
        ],
    )


def _demo_answer(mode: Literal["chat", "rag", "invoice"], input_text: str) -> str:
    if mode == "chat":
        return f"Sandbox chat response: I can help explore “{input_text}”."
    if mode == "rag":
        return f"Sandbox retrieval response: simulated context relevant to “{input_text}”."
    return f"Sandbox invoice extraction: I found a demo invoice signal in “{input_text}”."


__all__ = [
    "DemoQueryRequest",
    "DemoQueryResponse",
    "DemoQueryResult",
    "DemoQueryRunner",
    "router",
]
