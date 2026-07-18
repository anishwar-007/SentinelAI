"""Register Platform persistence consumers on an execution stream."""

from sentinelai.execution_stream import (
    ExecutionCancelled,
    ExecutionCompleted,
    ExecutionEventSubscriber,
    ExecutionFailed,
    ExecutionStarted,
    ExecutionStream,
    TraceCompleted,
)
from sentinelai.repositories.execution_lifecycle_repository import (
    ExecutionLifecycleRepository,
)
from sentinelai.repositories.execution_repository import ExecutionRepository
from sentinelai_platform.event_subscribers.execution import (
    ExecutionCancelledSubscriber,
    ExecutionCompletedSubscriber,
    ExecutionFailedSubscriber,
    ExecutionStartedSubscriber,
)
from sentinelai_platform.event_subscribers.trace import TraceCompletedSubscriber
from sentinelai_platform.execution_store import TracePersister


def register_persistence_subscribers(
    stream: ExecutionStream,
    *,
    executions: ExecutionLifecycleRepository,
    snapshots: ExecutionRepository,
    trace_persister: TracePersister,
) -> tuple[ExecutionEventSubscriber, ...]:
    """Attach the current Platform persistence projections to a stream."""
    subscribers: tuple[ExecutionEventSubscriber, ...] = (
        ExecutionStartedSubscriber(executions),
        ExecutionCompletedSubscriber(executions, snapshots),
        ExecutionFailedSubscriber(executions, snapshots),
        ExecutionCancelledSubscriber(executions, snapshots),
        TraceCompletedSubscriber(trace_persister),
    )
    stream.subscribe(ExecutionStarted, subscribers[0])
    stream.subscribe(ExecutionCompleted, subscribers[1])
    stream.subscribe(ExecutionFailed, subscribers[2])
    stream.subscribe(ExecutionCancelled, subscribers[3])
    stream.subscribe(TraceCompleted, subscribers[4])
    return subscribers
