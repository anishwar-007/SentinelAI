import json
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from examples.reference_runtime.analysis.analyzer import RootCauseAnalyzer, unknown_analysis
from examples.reference_runtime.analysis.schemas import RootCauseAnalysis
from examples.reference_runtime.executor import Executor
from examples.reference_runtime.planner.planner import Planner
from examples.reference_runtime.planner.schemas import Plan
from examples.reference_runtime.retriever.registry import DocumentNotFoundError, DocumentRegistry
from examples.reference_runtime.retriever.retriever import DocumentRetriever
from examples.reference_runtime.retriever.schemas import IndexedDocument
from examples.reference_runtime.schemas import InvoiceExtraction, LLMResponse
from examples.reference_runtime.verifier.schemas import VerificationResult
from examples.reference_runtime.verifier.verifier import Verifier
from sentinelai import execution

__all__ = [
    "AIOrchestrator",
    "DocumentNotFoundError",
    "EmptyQueryError",
    "IndexOutcome",
    "RunOutcome",
]

VerificationStatus = Literal["ok", "unknown"]


class EmptyQueryError(ValueError):
    pass


class RunOutcome(BaseModel):
    intent: str
    confidence: float
    result: Any
    verification: VerificationResult | None = None
    verification_status: VerificationStatus = "ok"
    analysis: RootCauseAnalysis | None = None


class IndexOutcome(BaseModel):
    document: IndexedDocument
    deduplicated: bool = False


def _index_query(
    content: str,
    document_id: str | None = None,
    *,
    filename: str | None = None,
    source: str | None = None,
) -> str:
    del content, document_id
    return f"index_document:{filename or source or 'untitled.txt'}"


def _index_metadata(
    content: str,
    document_id: str | None = None,
    *,
    filename: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    del content
    return {
        "action": "index_document",
        "document_id": document_id,
        "filename": filename,
        "source": source,
    }


class AIOrchestrator:
    def __init__(
        self,
        planner: Planner,
        executor: Executor,
        retriever: DocumentRetriever,
        verifier: Verifier,
        analyzer: RootCauseAnalyzer,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._retriever = retriever
        self._verifier = verifier
        self._analyzer = analyzer

    @property
    def registry(self) -> DocumentRegistry:
        return self._retriever.registry

    async def run(self, query: str) -> RunOutcome:
        cleaned = query.strip()
        if not cleaned:
            raise EmptyQueryError("Query must not be empty.")
        return await self._run_observed(cleaned)

    @execution("query")
    async def _run_observed(self, query: str) -> RunOutcome:
        verification_status: VerificationStatus = "ok"
        plan = await self._planner.plan(query)
        execution_result = await self._executor.execute(plan, query)

        if isinstance(execution_result.output, LLMResponse):
            verification, verification_status = await self._verify_execution(
                query=query,
                output=execution_result.output,
                retrieved_context=execution_result.retrieved_context,
            )
        else:
            verification = None

        analysis = await self._analyze_execution(
            query=query,
            plan=plan,
            output=execution_result.output,
            retrieved_context=execution_result.retrieved_context,
            verification=verification,
        )
        return RunOutcome(
            intent=plan.intent,
            confidence=plan.confidence,
            result=self._serialize_result(execution_result.output),
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
    ) -> RootCauseAnalysis:
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
    ) -> IndexOutcome:
        cleaned = content.strip()
        if not cleaned:
            raise EmptyQueryError("Document content must not be empty.")
        return await self._index_document_observed(
            cleaned,
            document_id,
            filename=filename,
            source=source,
        )

    @execution(
        "index_document",
        query=_index_query,
        intent="document_index",
        metadata=_index_metadata,
        include_snapshot=False,
    )
    async def _index_document_observed(
        self,
        content: str,
        document_id: str | None = None,
        *,
        filename: str | None = None,
        source: str | None = None,
    ) -> IndexOutcome:
        outcome = await self._retriever.index_document(
            content,
            document_id=document_id,
            filename=filename,
            source=source,
        )
        return IndexOutcome(
            document=outcome.document,
            deduplicated=outcome.deduplicated,
        )

    async def list_documents(self) -> list[IndexedDocument]:
        return await self.registry.list_documents()

    async def get_document(self, document_id: str) -> IndexedDocument:
        return await self.registry.get_document(UUID(document_id))

    @staticmethod
    def _serialize_result(result: Any) -> Any:
        if isinstance(result, InvoiceExtraction):
            return result.model_dump(mode="json")
        if isinstance(result, LLMResponse):
            return {
                "request_id": result.request_id,
                "model": result.model,
                "response": result.response,
                "usage": result.usage,
                "latency_ms": result.latency_ms,
            }
        if hasattr(result, "model_dump"):
            return result.model_dump(mode="json")
        return result
