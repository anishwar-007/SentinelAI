from examples.reference_runtime.llm import OpenRouterClient
from examples.reference_runtime.planner.prompts import plan_user_query_prompt
from examples.reference_runtime.planner.schemas import Plan
from examples.reference_runtime.structured import parse_structured
from sentinelai import observe


class Planner:
    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    @observe("planner", capture="plan", prompt_keys="planner")
    async def plan(self, user_query: str) -> Plan:
        prompt = plan_user_query_prompt(user_query)
        result = await self._client.generate(prompt)
        return parse_structured(result.response, Plan, result.request_id)
