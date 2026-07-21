from typing import assert_never

from pydantic import BaseModel

from examples.reference_runtime.invoice import InvoiceExtractor
from examples.reference_runtime.llm import LLMClient
from examples.reference_runtime.planner.schemas import Plan
from examples.reference_runtime.retriever.retriever import (
    DocumentRetriever,
    format_retrieved_context,
    inject_context,
)
from examples.reference_runtime.retriever.schemas import RetrieverResult
from examples.reference_runtime.schemas import InvoiceExtraction, LLMResponse
from sentinelai import span


class ExecutionResult(BaseModel):
    output: LLMResponse | InvoiceExtraction
    retrieved_context: str | None = None
    retrieval_result: RetrieverResult | None = None


class Executor:
    def __init__(
        self,
        client: LLMClient,
        invoice_extractor: InvoiceExtractor | None = None,
        retriever: DocumentRetriever | None = None,
    ) -> None:
        self._client = client
        self._invoice_extractor = invoice_extractor or InvoiceExtractor(client)
        self._retriever = retriever

    @span("executor")
    async def execute(
        self,
        plan: Plan,
        user_query: str,
    ) -> ExecutionResult:
        if plan.intent == "chat":
            chat_output: LLMResponse | InvoiceExtraction = await self._client.generate(
                user_query
            )
            return ExecutionResult(output=chat_output)
        if plan.intent == "invoice_extraction":
            invoice_output: LLMResponse | InvoiceExtraction = (
                await self._invoice_extractor.extract(user_query)
            )
            return ExecutionResult(output=invoice_output)
        if plan.intent == "retrieval":
            return await self._run_retrieval(user_query)
        assert_never(plan.intent)

    async def _run_retrieval(self, user_query: str) -> ExecutionResult:
        if self._retriever is None:
            raise RuntimeError("Retriever is not configured for this executor.")

        retrieval = await self._retriever.search(user_query)
        context = format_retrieved_context(retrieval)
        prompt = inject_context(user_query, retrieval)
        output = await self._client.generate(prompt)
        return ExecutionResult(
            output=output,
            retrieved_context=context or None,
            retrieval_result=retrieval,
        )
