import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.errors import LLMError
from app.executor import Executor
from app.planner.planner import Planner
from app.schemas import InvoiceExtraction, LLMResponse
from app.tracing.tracer import DEFAULT_TRACES_DIR, Tracer


class TraceNotFoundError(LookupError):
    pass


class EmptyQueryError(ValueError):
    pass


class RunResult(BaseModel):
    trace_id: str
    intent: str
    confidence: float
    result: Any
    latency_ms: float


class AIOrchestrator:
    def __init__(
        self,
        planner: Planner,
        executor: Executor,
        traces_dir: str = DEFAULT_TRACES_DIR,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._traces_dir = traces_dir

    async def run(self, query: str) -> RunResult:
        cleaned = query.strip()
        if not cleaned:
            raise EmptyQueryError("Query must not be empty.")

        tracer = Tracer(output_dir=self._traces_dir)
        plan = None
        result: LLMResponse | InvoiceExtraction | None = None

        with tracer.trace(metadata={"query": cleaned}):
            plan = await self._planner.plan(cleaned)
            result = await self._executor.execute(plan, cleaned)

        trace = tracer.current_trace
        if trace is None or plan is None or result is None:
            raise LLMError("Orchestrator finished without a trace or result.")

        return RunResult(
            trace_id=trace.trace_id,
            intent=plan.intent,
            confidence=plan.confidence,
            result=self._serialize_result(result),
            latency_ms=trace.total_latency_ms or 0.0,
        )

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        path = Path(self._traces_dir) / f"{trace_id}.json"
        if not path.is_file():
            raise TraceNotFoundError(f"Trace not found: {trace_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise LLMError(f"Trace file is corrupt: {trace_id}")
        return data

    @staticmethod
    def _serialize_result(result: LLMResponse | InvoiceExtraction) -> Any:
        if isinstance(result, InvoiceExtraction):
            return result.model_dump(mode="json")
        return {
            "request_id": result.request_id,
            "model": result.model,
            "response": result.response,
            "usage": result.usage,
            "latency_ms": result.latency_ms,
        }
