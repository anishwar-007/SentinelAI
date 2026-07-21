from examples.reference_runtime.llm import LLMClient
from examples.reference_runtime.planner.prompts import plan_user_query_prompt
from examples.reference_runtime.planner.schemas import Plan
from examples.reference_runtime.structured import parse_structured
from sentinelai import span


class Planner:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    @span("planner")
    async def plan(self, user_query: str) -> Plan:
        prompt = plan_user_query_prompt(user_query)
        result = await self._client.generate(prompt, json_mode=True)
        return parse_structured(result.response, Plan, result.request_id)
