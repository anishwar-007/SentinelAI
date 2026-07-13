import json

from pydantic import ValidationError

from app.llm import (
    ModelStructuredOutputError,
    ModelValidationError,
    OpenRouterClient,
)
from app.logger import get_logger
from app.planner.prompts import plan_user_query_prompt
from app.planner.schemas import Plan

logger = get_logger()


class Planner:

    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    async def plan(self, user_query: str) -> Plan:
        logger.info("planner.start query_chars=%s", len(user_query))
        prompt = plan_user_query_prompt(user_query)
        result = await self._client.generate(prompt)
        plan = self._parse_plan(result.response, result.request_id)
        logger.info(
            "planner.success request_id=%s intent=%s confidence=%s",
            result.request_id,
            plan.intent,
            plan.confidence,
        )
        return plan

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
