import asyncio
import json

from examples.reference_runtime.config import load_settings
from examples.reference_runtime.errors import LLMError
from examples.reference_runtime.executor import Executor
from examples.reference_runtime.invoice import InvoiceExtractor
from examples.reference_runtime.llm import create_llm_client
from examples.reference_runtime.planner.planner import Planner
from examples.reference_runtime.planner.schemas import Plan
from examples.reference_runtime.schemas import InvoiceExtraction, LLMResponse
from sentinelai import (
    Contracts,
    configure,
    execution,
    get_current_execution_latency_ms,
    get_current_trace_id,
)
from sentinelai.execution_stream import InMemoryExecutionStream


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


def print_trace_summary(trace_id: str, latency_ms: float) -> None:
    print("=" * 48)
    print("TRACE")
    print(f"TRACE ID       : {trace_id}")
    print(f"TOTAL LATENCY  : {latency_ms:.0f}ms")
    print("=" * 48)


@execution("cli.query")
async def run_query(
    planner: Planner,
    executor: Executor,
    user_query: str,
) -> tuple[Plan, LLMResponse | InvoiceExtraction]:
    plan = await planner.plan(user_query)
    result = await executor.execute(plan, user_query)
    return plan, result.output


async def main() -> None:
    settings = load_settings()
    configure(
        publisher=InMemoryExecutionStream(),
        model_info=Contracts.ModelInfo(
            provider=settings.model_provider,
            model_name=settings.model,
        ),
    )

    async with create_llm_client(settings) as client:
        planner = Planner(client)
        executor = Executor(client, InvoiceExtractor(client))

        user_query = input("Enter Query: ").strip()
        if not user_query:
            print("No query entered. Exiting.")
            return

        try:
            plan, result = await run_query(planner, executor, user_query)
            print_plan(plan)
            print_result(result)
        except LLMError as exc:
            print(f"Error: {exc}")

        trace_id = get_current_trace_id()
        latency_ms = get_current_execution_latency_ms()
        if trace_id is not None and latency_ms is not None:
            print_trace_summary(trace_id, latency_ms)


if __name__ == "__main__":
    asyncio.run(main())
