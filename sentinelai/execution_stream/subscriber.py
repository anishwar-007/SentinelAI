"""Consumer-side execution stream contract."""

from typing import Protocol

from sentinelai.execution_stream.event import ExecutionEvent


class ExecutionEventSubscriber(Protocol):
    """Consumes execution facts without coupling producers to side effects."""

    async def handle(self, event: ExecutionEvent) -> None:
        """Handle one event delivered by an execution stream."""
        ...
