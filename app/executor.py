from app.llm import OpenRouterClient
from app.logger import get_logger
from app.planner.schemas import Plan
from app.schemas import InvoiceExtraction, LLMResponse

logger = get_logger()


class Executor:

    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    async def execute(
        self,
        plan: Plan,
        user_query: str,
    ) -> LLMResponse | InvoiceExtraction:
        logger.info(
            "executor.start intent=%s query_chars=%s",
            plan.intent,
            len(user_query),
        )
        if plan.intent == "chat":
            result = await self._client.generate(user_query)
            logger.info(
                "executor.success intent=%s request_id=%s",
                plan.intent,
                result.request_id,
            )
            return result
        if plan.intent == "invoice_extraction":
            invoice = await self._client.extract_invoice(user_query)
            logger.info("executor.success intent=%s", plan.intent)
            return invoice
        raise ValueError(f"Unsupported intent: {plan.intent!r}")
