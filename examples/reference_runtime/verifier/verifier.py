from examples.reference_runtime.llm import LLMClient
from examples.reference_runtime.structured import parse_structured
from examples.reference_runtime.verifier.prompts import verification_prompt
from examples.reference_runtime.verifier.schemas import VerificationResult
from sentinelai import span


class Verifier:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    @span("verifier")
    async def verify(
        self,
        query: str,
        context: str,
        answer: str,
    ) -> VerificationResult:
        prompt = verification_prompt(query=query, context=context, answer=answer)
        result = await self._client.generate(prompt, json_mode=True)
        return parse_structured(
            result.response,
            VerificationResult,
            result.request_id,
        )
