import asyncio
import json

from app.config import load_settings
from app.errors import LLMError
from app.executor import Executor
from app.invoice import InvoiceExtractor
from app.llm import OpenRouterClient
from app.planner.planner import Planner
from app.planner.schemas import Plan
from app.schemas import InvoiceExtraction, LLMResponse
from app.tracing.schemas import Trace
from app.tracing.tracer import Tracer


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


def print_trace_summary(trace: Trace, saved_path: str) -> None:
    print("=" * 48)
    print("TRACE")
    print(f"TRACE ID       : {trace.trace_id}")
    print(f"TOTAL LATENCY  : {trace.total_latency_ms:.0f}ms")
    print(f"SPANS          : {len(trace.spans)}")
    print(f"SAVED          : {saved_path}")
    print("=" * 48)


async def main() -> None:
    settings = load_settings()

    async with OpenRouterClient(
        api_key=settings.openrouter_api_key,
        model=settings.model,
        base_url=settings.base_url,
    ) as client:
        planner = Planner(client)
        executor = Executor(client, InvoiceExtractor(client))
        tracer = Tracer()

        user_query = input("Enter Query: ").strip()
        if not user_query:
            print("No query entered. Exiting.")
            return

        with tracer.trace(metadata={"query": user_query}):
            try:
                plan = await planner.plan(user_query)
                print_plan(plan)
                result = await executor.execute(plan, user_query)
                print_result(result)
            except LLMError as exc:
                print(f"Error: {exc}")

        if tracer.current_trace is not None and tracer.saved_path is not None:
            print_trace_summary(tracer.current_trace, str(tracer.saved_path))


if __name__ == "__main__":
    asyncio.run(main())
