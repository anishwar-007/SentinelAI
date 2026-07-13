from app.llm import OpenRouterClient
from app.planner.schemas import Plan
from app.schemas import InvoiceExtraction, LLMResponse


class Executor:

    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    async def execute(
        self,
        plan: Plan,
        user_query: str,
    ) -> LLMResponse | InvoiceExtraction:
        if plan.intent == "chat":
            return await self._client.generate(user_query)
        if plan.intent == "invoice_extraction":
            return await self._client.extract_invoice(user_query)
        raise ValueError(f"Unsupported intent: {plan.intent!r}")
