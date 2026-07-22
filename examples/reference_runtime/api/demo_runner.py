"""Bridge Platform demo routes to the reference-runtime orchestrator."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from examples.reference_runtime.errors import LLMError
from examples.reference_runtime.services.orchestrator import AIOrchestrator, RunOutcome
from sentinelai import (
    ModelInfo,
    get_current_execution_id,
    get_current_execution_latency_ms,
    get_current_trace_id,
)
from sentinelai.contracts import ExecutionSnapshot, Trace
from sentinelai_platform.api.demo import DemoQueryRequest, DemoQueryResult
from sentinelai_platform.execution_store import TracePersister

_SANDBOX_METADATA = {"environment": "sandbox", "source": "public_demo"}
_Mode = Literal["chat", "rag", "invoice"]


def build_demo_query_runner(
    orchestrator: AIOrchestrator,
    *,
    trace_persister: TracePersister,
):
    async def run_demo_query(payload: DemoQueryRequest) -> DemoQueryResult:
        started_at = datetime.now(UTC)
        outcome = await orchestrator.run(payload.input)
        execution_id = get_current_execution_id()
        trace_id = get_current_trace_id()
        latency_ms = get_current_execution_latency_ms() or 0.0
        if execution_id is None or trace_id is None:
            raise LLMError("Orchestrator finished without execution correlation.")

        answer = _answer_from_outcome(outcome)
        mode = _mode_from_intent(outcome.intent)
        trace = await _load_real_trace(trace_persister, UUID(str(trace_id)))
        snapshot = ExecutionSnapshot(
            execution_id=execution_id,
            query=payload.input,
            response={"answer": answer, "result": outcome.result},
            trace_id=UUID(str(trace_id)),
            model_info=ModelInfo(
                provider="sentinelai-reference",
                model_name="orchestrator",
            ),
            created_at=started_at,
            metadata={
                **_SANDBOX_METADATA,
                "execution_name": "public_demo",
                "pipeline": "reference_runtime",
            },
            execution_status="completed",
            intent=outcome.intent,
        )
        return DemoQueryResult(
            execution_id=execution_id,
            answer=answer,
            latency_ms=latency_ms,
            mode=mode,
            snapshot=snapshot,
            trace=trace,
        )

    return run_demo_query


async def _load_real_trace(persister: TracePersister, trace_id: UUID) -> Trace:
    """Load the SDK-emitted trace and tag it for demo read routes."""
    try:
        raw = await persister.load(trace_id)
    except FileNotFoundError as exc:
        raise LLMError(f"Persisted trace not found for demo response: {trace_id}") from exc

    trace = Trace.model_validate(raw)
    metadata = {
        **dict(trace.metadata),
        **_SANDBOX_METADATA,
        "pipeline": "reference_runtime",
    }
    return trace.model_copy(update={"metadata": metadata})


def _mode_from_intent(intent: str) -> _Mode:
    if intent == "retrieval":
        return "rag"
    if intent == "invoice_extraction":
        return "invoice"
    return "chat"


def _answer_from_outcome(outcome: RunOutcome) -> str:
    result: Any = outcome.result
    if isinstance(result, dict):
        if isinstance(result.get("response"), str):
            return result["response"]
        if isinstance(result.get("answer"), str):
            return result["answer"]
        return json.dumps(result)
    return str(result)
