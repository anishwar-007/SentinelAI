from typing import assert_never

from app.invoice import InvoiceExtractor
from app.llm import OpenRouterClient
from app.planner.schemas import Plan
from app.schemas import InvoiceExtraction, LLMResponse
from app.tracing.decorators import trace_span


class Executor:
    def __init__(
        self,
        client: OpenRouterClient,
        invoice_extractor: InvoiceExtractor | None = None,
    ) -> None:
        self._client = client
        self._invoice_extractor = invoice_extractor or InvoiceExtractor(client)

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
        assert_never(plan.intent)
