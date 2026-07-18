from examples.reference_runtime.llm import OpenRouterClient
from examples.reference_runtime.structured import parse_structured
from examples.reference_runtime.verifier.prompts import verification_prompt
from examples.reference_runtime.verifier.schemas import VerificationResult
from sentinelai import observe


class Verifier:
    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    @observe("verifier", capture="verification", prompt_keys="verifier")
    async def verify(
        self,
        query: str,
        context: str,
        answer: str,
    ) -> VerificationResult:
        prompt = verification_prompt(query=query, context=context, answer=answer)
        result = await self._client.generate(prompt)
        return parse_structured(
            result.response,
            VerificationResult,
            result.request_id,
        )
