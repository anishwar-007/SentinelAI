import asyncio
import json

from app.config import load_settings
from app.executor import Executor
from app.llm import LLMError, OpenRouterClient
from app.logger import get_logger, setup_logging
from app.planner.planner import Planner
from app.planner.schemas import Plan
from app.schemas import InvoiceExtraction, LLMResponse

logger = get_logger()


def print_plan(plan: Plan) -> None:
    print("=" * 48)
    print("PLAN")
    print(f"INTENT     : {plan.intent}")
    print(f"CONFIDENCE : {plan.confidence}")
    print(f"REASONING  : {plan.reasoning}")
    print("=" * 48)


def print_chat_result(result: LLMResponse) -> None:
    print("=" * 48)
    print(f"REQUEST ID : {result.request_id}")
    print(f"MODEL      : {result.model}")
    print(f"LATENCY    : {result.latency_ms:.0f}ms")
    print(f"TOKENS     : {result.usage}")
    print(f"RESPONSE   : {result.response}")
    print("=" * 48)


def print_invoice_result(invoice: InvoiceExtraction) -> None:
    print("=" * 48)
    print("INVOICE EXTRACTION")
    print(json.dumps(invoice.model_dump(mode="json"), indent=2))
    print("=" * 48)


def print_result(result: LLMResponse | InvoiceExtraction) -> None:
    if isinstance(result, InvoiceExtraction):
        print_invoice_result(result)
    else:
        print_chat_result(result)


async def main() -> None:
    setup_logging()
    settings = load_settings()

    client = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        model=settings.model,
    )
    planner = Planner(client)
    executor = Executor(client)

    user_query = input("Enter Query: ").strip()
    if not user_query:
        print("No query entered. Exiting.")
        return

    logger.info("request.start query_chars=%s", len(user_query))

    try:
        plan = await planner.plan(user_query)
        print_plan(plan)
        result = await executor.execute(plan, user_query)
        print_result(result)
        logger.info("request.success intent=%s", plan.intent)
    except LLMError as exc:
        logger.error("request.failed error=%s", exc)
        print(f"Error: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
