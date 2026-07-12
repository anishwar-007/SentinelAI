import asyncio
import json

from app.config import load_settings
from app.llm import LLMError, OpenRouterClient
from app.schemas import InvoiceExtraction, LLMResponse


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


def read_multiline_invoice() -> str:

    print("Paste invoice text, then type END on its own line:")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()


async def run_chat(client: OpenRouterClient) -> None:
    prompt = input("Enter Prompt: ").strip()
    if not prompt:
        print("No prompt entered. Exiting.")
        return

    result = await client.generate(prompt)
    print_chat_result(result)


async def run_extract_invoice(client: OpenRouterClient) -> None:
    text = read_multiline_invoice()
    if not text:
        print("No invoice text entered. Exiting.")
        return

    invoice = await client.extract_invoice(text)
    print_invoice_result(invoice)


async def main() -> None:
    settings = load_settings()

    client = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        model=settings.model,
    )

    print("Choose task")
    print("1. Chat")
    print("2. Extract Invoice")
    choice = input("> ").strip()

    try:
        if choice == "1":
            await run_chat(client)
        elif choice == "2":
            await run_extract_invoice(client)
        else:
            print("Invalid choice. Enter 1 or 2.")
    except LLMError as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
