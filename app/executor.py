from typing import assert_never

from app.invoice import InvoiceExtractor
from app.llm import OpenRouterClient
from app.planner.schemas import Plan
from app.retriever.retriever import DocumentRetriever, inject_context
from app.schemas import InvoiceExtraction, LLMResponse
from app.tracing.decorators import trace_span


class Executor:
    def __init__(
        self,
        client: OpenRouterClient,
        invoice_extractor: InvoiceExtractor | None = None,
        retriever: DocumentRetriever | None = None,
    ) -> None:
        self._client = client
        self._invoice_extractor = invoice_extractor or InvoiceExtractor(client)
        self._retriever = retriever

    @trace_span("executor")
    async def execute(
        self,
        plan: Plan,
        user_query: str,
    ) -> LLMResponse | InvoiceExtraction:
        if plan.intent == "chat":
            return await self._client.generate(user_query)
        if plan.intent == "invoice_extraction":
            return await self._invoice_extractor.extract(user_query)
        if plan.intent == "retrieval":
            return await self._run_retrieval(user_query)
        assert_never(plan.intent)

    async def _run_retrieval(self, user_query: str) -> LLMResponse:
        if self._retriever is None:
            raise RuntimeError("Retriever is not configured for this executor.")

        retrieval = await self._retriever.search(user_query)
        prompt = inject_context(user_query, retrieval)
        return await self._client.generate(prompt)
