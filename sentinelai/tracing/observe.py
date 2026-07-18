"""Public instrumentation decorator."""

from sentinelai.tracing.decorators import trace_span

# Public name for customer applications. The historical decorator name remains
# available as a compatibility alias.
observe = trace_span

__all__ = ["observe", "trace_span"]
