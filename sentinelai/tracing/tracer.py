import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sentinelai.contracts import Span, SpanStatus, Trace
from sentinelai.tracing.context import TraceContext


class Tracer:
    """Collect an in-memory trace.

    Completed traces become immutable execution-stream facts. Consumers decide
    whether to persist, analyze, replay, or forward those facts.
    """

    def __init__(self) -> None:
        self._trace: Trace | None = None
        self._context_token: Any = None

    @property
    def current_trace(self) -> Trace | None:
        return self._trace

    def start_trace(self, metadata: dict[str, Any] | None = None) -> Trace:
        self._trace = Trace(
            trace_id=str(uuid.uuid4()),
            started_at=datetime.now(UTC),
            metadata=metadata or {},
        )
        self._context_token = TraceContext.set_tracer(self)
        return self._trace

    def end_trace(self) -> Trace:
        if self._trace is None:
            raise RuntimeError("No active trace to end.")

        self._trace.ended_at = datetime.now(UTC)
        elapsed = self._trace.ended_at - self._trace.started_at
        self._trace.total_latency_ms = elapsed.total_seconds() * 1000
        if self._context_token is not None:
            TraceContext.reset_tracer(self._context_token)
            self._context_token = None
        else:
            TraceContext.clear()

        return self._trace

    @contextmanager
    def trace(self, metadata: dict[str, Any] | None = None) -> Iterator["Tracer"]:
        self.start_trace(metadata)
        try:
            yield self
        finally:
            self.end_trace()

    def start_span(self, name: str, payload: Any = None) -> Span:
        if self._trace is None:
            raise RuntimeError("No active trace. Call start_trace() first.")

        span = Span(
            id=str(uuid.uuid4()),
            name=name,
            parent_span_id=TraceContext.current_span_id(),
            start_time=datetime.now(UTC),
            input=payload,
            status="running",
        )
        self._trace.spans.append(span)
        TraceContext.push_span(span.id)
        return span

    def end_span(
        self,
        span: Span,
        *,
        output: Any = None,
        model: str | None = None,
        tokens: dict[str, Any] | None = None,
        status: SpanStatus = "ok",
        error: str | None = None,
    ) -> Span:
        span.end_time = datetime.now(UTC)
        span.latency_ms = (span.end_time - span.start_time).total_seconds() * 1000
        span.output = output
        span.model = model
        span.tokens = tokens
        span.status = status
        span.error = error
        TraceContext.pop_span(span.id)
        return span

    def serialize(self) -> dict[str, Any]:
        if self._trace is None:
            raise RuntimeError("No active trace to serialize.")
        return self._trace.model_dump(mode="json")

