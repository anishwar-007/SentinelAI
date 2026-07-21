"""Public ambient correlation getters backed by internal ContextVars."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

from sentinelai.execution.active import get_active_execution
from sentinelai.tracing.context import TraceContext


@dataclass(frozen=True, slots=True)
class _Correlation:
    execution_id: UUID
    trace_id: str | None
    latency_ms: float | None


_last_correlation: ContextVar[_Correlation | None] = ContextVar(
    "sentinelai_last_correlation",
    default=None,
)


def get_current_execution_id() -> UUID | None:
    """Return the active or most recently completed execution identifier."""
    context = get_active_execution()
    if context is not None:
        execution_id = getattr(context, "execution_id", None)
        return execution_id if isinstance(execution_id, UUID) else None
    correlation = _last_correlation.get()
    return correlation.execution_id if correlation is not None else None


def get_current_trace_id() -> str | None:
    """Return the active or most recently completed trace identifier."""
    trace = TraceContext.get_trace()
    if trace is not None:
        return trace.trace_id
    correlation = _last_correlation.get()
    return correlation.trace_id if correlation is not None else None


def get_current_execution_latency_ms() -> float | None:
    """Return latency for the most recently completed execution in this context."""
    correlation = _last_correlation.get()
    return correlation.latency_ms if correlation is not None else None


def _clear_completed_correlation() -> None:
    _last_correlation.set(None)


def _set_completed_correlation(
    *,
    execution_id: UUID,
    trace_id: str | None,
    latency_ms: float | None,
) -> None:
    _last_correlation.set(
        _Correlation(
            execution_id=execution_id,
            trace_id=trace_id,
            latency_ms=latency_ms,
        )
    )


__all__ = [
    "get_current_execution_id",
    "get_current_execution_latency_ms",
    "get_current_trace_id",
]
