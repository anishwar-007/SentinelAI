"""Producer-side execution stream contract."""

from typing import Protocol

from sentinelai.execution_stream.event import ExecutionEvent


class ExecutionEventPublisher(Protocol):
    """Publishes immutable execution facts without knowing their consumers."""

    async def publish(self, event: ExecutionEvent) -> None:
        """Publish one event to the execution stream."""
        ...
