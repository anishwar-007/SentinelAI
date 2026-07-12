import asyncio

from app.config import load_settings
from app.llm import LLMError, OpenRouterClient
from app.schemas import LLMResponse


def print_result(result: LLMResponse) -> None:
    print("=" * 48)
    print(f"REQUEST ID : {result.request_id}")
    print(f"MODEL      : {result.model}")
    print(f"LATENCY    : {result.latency_ms:.0f}ms")
    print(f"TOKENS     : {result.usage}")
    print(f"RESPONSE   : {result.response}")
    print("=" * 48)


async def main() -> None:
    settings = load_settings()

    client = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        model=settings.model,
    )

    prompt = input("Enter Prompt: ").strip()
    if not prompt:
        print("No prompt entered. Exiting.")
        return

    try:
        result = await client.generate(prompt)
    except LLMError as exc:
        print(f"Error: {exc}")
        return

    print_result(result)


if __name__ == "__main__":
    asyncio.run(main())
