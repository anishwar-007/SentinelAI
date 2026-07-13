from app.llm import OpenRouterClient
from app.planner.prompts import plan_user_query_prompt
from app.planner.schemas import Plan
from app.structured import parse_structured
from app.tracing.decorators import trace_span


class Planner:
    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    @trace_span("planner")
    async def plan(self, user_query: str) -> Plan:
        prompt = plan_user_query_prompt(user_query)
        result = await self._client.generate(prompt)
        return parse_structured(result.response, Plan, result.request_id)
