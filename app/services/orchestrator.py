import json
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from app.analysis.analyzer import RootCauseAnalyzer, unknown_analysis
from app.analysis.schemas import RootCauseAnalysis
from app.errors import LLMError
from app.executor import Executor
from app.planner.planner import Planner
from app.planner.schemas import Plan
from app.retriever.registry import DocumentNotFoundError, DocumentRegistry
from app.retriever.retriever import DocumentRetriever
from app.retriever.schemas import IndexedDocument
from app.schemas import InvoiceExtraction, LLMResponse
from app.tracing.schemas import Trace
from app.tracing.tracer import DEFAULT_TRACES_DIR, Tracer
from app.verifier.schemas import VerificationResult
from app.verifier.verifier import Verifier

__all__ = [
    "AIOrchestrator",
    "DocumentNotFoundError",
    "EmptyQueryError",
    "IndexResult",
    "RunResult",
    "TraceNotFoundError",
]

VerificationStatus = Literal["ok", "unknown"]


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
    verification: VerificationResult | None = None
    verification_status: VerificationStatus = "ok"
    analysis: RootCauseAnalysis | None = None


class IndexResult(BaseModel):
    document: IndexedDocument
    trace_id: str
    latency_ms: float
    deduplicated: bool = False


class AIOrchestrator:
    def __init__(
        self,
        planner: Planner,
        executor: Executor,
        retriever: DocumentRetriever,
        verifier: Verifier,
        analyzer: RootCauseAnalyzer,
        traces_dir: str = DEFAULT_TRACES_DIR,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._retriever = retriever
        self._verifier = verifier
        self._analyzer = analyzer
        self._traces_dir = traces_dir

    @property
    def registry(self) -> DocumentRegistry:
        return self._retriever.registry

    async def run(self, query: str) -> RunResult:
        cleaned = query.strip()
        if not cleaned:
            raise EmptyQueryError("Query must not be empty.")

        tracer = Tracer(output_dir=self._traces_dir)
        plan = None
        output: LLMResponse | InvoiceExtraction | None = None
        verification: VerificationResult | None = None
        verification_status: VerificationStatus = "ok"
        analysis: RootCauseAnalysis | None = None

        with tracer.trace(metadata={"query": cleaned}):
            plan = await self._planner.plan(cleaned)
            execution = await self._executor.execute(plan, cleaned)
            output = execution.output
            verification, verification_status = await self._verify_execution(
                query=cleaned,
                output=output,
                retrieved_context=execution.retrieved_context,
            )
            analysis = await self._analyze_execution(
                query=cleaned,
                plan=plan,
                output=output,
                retrieved_context=execution.retrieved_context,
                verification=verification,
                trace=tracer.current_trace,
            )

        trace = tracer.current_trace
        if trace is None or plan is None or output is None:
            raise LLMError("Orchestrator finished without a trace or result.")

        return RunResult(
            trace_id=trace.trace_id,
            intent=plan.intent,
            confidence=plan.confidence,
            result=self._serialize_result(output),
            latency_ms=trace.total_latency_ms or 0.0,
            verification=verification,
            verification_status=verification_status,
            analysis=analysis,
        )

    async def _verify_execution(
        self,
        *,
        query: str,
        output: LLMResponse | InvoiceExtraction,
        retrieved_context: str | None,
    ) -> tuple[VerificationResult | None, VerificationStatus]:
        if not isinstance(output, LLMResponse):
            return None, "ok"

        try:
            result = await self._verifier.verify(
                query=query,
                context=retrieved_context or "",
                answer=output.response,
            )
            return result, "ok"
        except Exception:
            return None, "unknown"

    async def _analyze_execution(
        self,
        *,
        query: str,
        plan: Plan,
        output: LLMResponse | InvoiceExtraction,
        retrieved_context: str | None,
        verification: VerificationResult | None,
        trace: Trace | None,
    ) -> RootCauseAnalysis:
        if trace is None:
            return unknown_analysis("No active trace available for analysis.")

        answer = (
            output.response
            if isinstance(output, LLMResponse)
            else json.dumps(output.model_dump(mode="json"))
        )

        try:
            return await self._analyzer.analyze(
                query=query,
                plan=plan,
                retrieved_context=retrieved_context,
                answer=answer,
                verification=verification,
                trace=trace,
            )
        except Exception as exc:
            return unknown_analysis(f"Analyzer failed: {exc}")

    async def index_document(
        self,
        content: str,
        document_id: str | None = None,
        *,
        filename: str | None = None,
        source: str | None = None,
    ) -> IndexResult:
        cleaned = content.strip()
        if not cleaned:
            raise EmptyQueryError("Document content must not be empty.")

        tracer = Tracer(output_dir=self._traces_dir)
        outcome = None

        with tracer.trace(
            metadata={
                "action": "index_document",
                "document_id": document_id,
                "filename": filename,
                "source": source,
            }
        ):
            outcome = await self._retriever.index_document(
                cleaned,
                document_id=document_id,
                filename=filename,
                source=source,
            )

        trace = tracer.current_trace
        if trace is None or outcome is None:
            raise LLMError("Indexing finished without a trace.")

        return IndexResult(
            document=outcome.document,
            trace_id=trace.trace_id,
            latency_ms=trace.total_latency_ms or 0.0,
            deduplicated=outcome.deduplicated,
        )

    def list_documents(self) -> list[IndexedDocument]:
        return self.registry.list_documents()

    def get_document(self, document_id: str) -> IndexedDocument:
        return self.registry.get_document(UUID(document_id))

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
