"""Execution stream abstraction and process-local implementation."""

import asyncio
from typing import Protocol

from sentinelai.execution_stream.event import ExecutionEvent
from sentinelai.execution_stream.publisher import ExecutionEventPublisher
from sentinelai.execution_stream.subscriber import ExecutionEventSubscriber


class ExecutionStream(ExecutionEventPublisher, Protocol):
    """Publishes execution facts and manages event subscribers."""

    def subscribe(
        self,
        event_class: type[ExecutionEvent],
        subscriber: ExecutionEventSubscriber,
    ) -> None:
        """Subscribe a consumer to an event class and its subclasses."""
        ...

    def unsubscribe(
        self,
        event_class: type[ExecutionEvent],
        subscriber: ExecutionEventSubscriber,
    ) -> None:
        """Remove a previously registered subscription."""
        ...


class InMemoryExecutionStream:
    """Asynchronous in-process fan-out for local runtimes and tests.

    Subscriber calls are awaited together. A subscriber failure propagates to
    the publisher after all matching subscribers have had a chance to finish.
    """

    def __init__(self) -> None:
        self._subscriptions: list[
            tuple[type[ExecutionEvent], ExecutionEventSubscriber]
        ] = []

    def subscribe(
        self,
        event_class: type[ExecutionEvent],
        subscriber: ExecutionEventSubscriber,
    ) -> None:
        if any(
            registered_class is event_class and registered is subscriber
            for registered_class, registered in self._subscriptions
        ):
            return
        self._subscriptions.append((event_class, subscriber))

    def unsubscribe(
        self,
        event_class: type[ExecutionEvent],
        subscriber: ExecutionEventSubscriber,
    ) -> None:
        self._subscriptions = [
            (registered_class, registered)
            for registered_class, registered in self._subscriptions
            if not (
                registered_class is event_class
                and registered is subscriber
            )
        ]

    async def publish(self, event: ExecutionEvent) -> None:
        subscribers = tuple(
            subscriber
            for event_class, subscriber in self._subscriptions
            if isinstance(event, event_class)
        )
        if not subscribers:
            return
        results = await asyncio.gather(
            *(subscriber.handle(event) for subscriber in subscribers),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                raise result
