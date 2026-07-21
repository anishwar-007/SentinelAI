"""Frozen public instrumentation vocabulary."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from sentinelai.sdk.configure import configure
from sentinelai.sdk.correlation import (
    get_current_execution_id,
    get_current_execution_latency_ms,
    get_current_trace_id,
)
from sentinelai.sdk.observe_execution import observe_execution
from sentinelai.tracing.decorators import trace_span

P = ParamSpec("P")
R = TypeVar("R")


def execution(
    name: str,
    **options: Any,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Mark an async callable as one AI execution boundary."""
    return observe_execution(execution_name=name, **options)


def span(
    name: str,
    **options: Any,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Observe one operation inside the active execution."""
    return trace_span(name, **options)


class Sentinel:
    """Small facade over SentinelAI's process-wide instrumentation API."""

    configure = staticmethod(configure)
    execution = staticmethod(execution)
    span = staticmethod(span)
    get_current_execution_id = staticmethod(get_current_execution_id)
    get_current_trace_id = staticmethod(get_current_trace_id)
    get_current_execution_latency_ms = staticmethod(
        get_current_execution_latency_ms
    )


__all__ = ["Sentinel", "execution", "span"]
