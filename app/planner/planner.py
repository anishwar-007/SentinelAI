import json

from pydantic import ValidationError

from app.llm import (
    ModelStructuredOutputError,
    ModelValidationError,
    OpenRouterClient,
)
from app.planner.prompts import plan_user_query_prompt
from app.planner.schemas import Plan


class Planner:

    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    async def plan(self, user_query: str) -> Plan:
        prompt = plan_user_query_prompt(user_query)
        result = await self._client.generate(prompt)
        return self._parse_plan(result.response, result.request_id)

    def _parse_plan(self, content: str, request_id: str) -> Plan:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ModelStructuredOutputError(
                f"Request {request_id}: Planner did not return valid JSON. "
                f"Raw content: {content!r}"
            ) from exc

        if not isinstance(data, dict):
            raise ModelStructuredOutputError(
                f"Request {request_id}: Expected a JSON object, got {type(data).__name__}."
            )

        try:
            return Plan.model_validate(data)
        except ValidationError as exc:
            raise ModelValidationError(
                f"Request {request_id}: Plan JSON failed validation: {exc}"
            ) from exc
