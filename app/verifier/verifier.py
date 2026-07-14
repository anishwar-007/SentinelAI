from app.llm import OpenRouterClient
from app.structured import parse_structured
from app.tracing.decorators import trace_span
from app.verifier.prompts import verification_prompt
from app.verifier.schemas import VerificationResult


class Verifier:
    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    @trace_span("verifier")
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
