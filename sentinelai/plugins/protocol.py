from typing import Any, Protocol


class Plugin(Protocol):
    """Contract for framework-specific SentinelAI instrumentation plugins.

    Future LangGraph, CrewAI, OpenAI Agents SDK, PydanticAI, and LlamaIndex
    plugins can implement this protocol without changing SDK core.
    """

    def instrument(self, target: Any) -> Any:
        """Wrap or register ``target`` so SentinelAI observes its executions."""
        ...
