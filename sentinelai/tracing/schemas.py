"""Deprecated compatibility imports.

Import shared DTOs from :mod:`sentinelai.contracts` instead.
"""

from sentinelai.contracts.tracing import (
    Span,
    SpanRecord,
    SpanStatus,
    Trace,
    TraceRecord,
)

__all__ = [
    "Span",
    "SpanRecord",
    "SpanStatus",
    "Trace",
    "TraceRecord",
]
