from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.tracing.schemas import Trace
    from app.tracing.tracer import Tracer

_current_tracer: ContextVar["Tracer | None"] = ContextVar(
    "current_tracer",
    default=None,
)
_span_stack: ContextVar[tuple[str, ...]] = ContextVar(
    "span_stack",
    default=(),
)


class TraceContext:
    @staticmethod
    def set_tracer(tracer: "Tracer") -> Token["Tracer | None"]:
        _span_stack.set(())
        return _current_tracer.set(tracer)

    @staticmethod
    def reset_tracer(token: Token["Tracer | None"]) -> None:
        _current_tracer.reset(token)
        _span_stack.set(())

    @staticmethod
    def get_tracer() -> "Tracer | None":
        return _current_tracer.get()

    @staticmethod
    def get_trace() -> "Trace | None":
        tracer = _current_tracer.get()
        if tracer is None:
            return None
        return tracer.current_trace

    @staticmethod
    def current_span_id() -> str | None:
        stack = _span_stack.get()
        if not stack:
            return None
        return stack[-1]

    @staticmethod
    def push_span(span_id: str) -> None:
        stack = _span_stack.get()
        _span_stack.set(stack + (span_id,))

    @staticmethod
    def pop_span(span_id: str) -> None:
        stack = _span_stack.get()
        if not stack:
            raise RuntimeError(
                f"Span stack is empty; cannot pop span {span_id!r}."
            )
        if stack[-1] != span_id:
            raise RuntimeError(
                f"Span stack mismatch: expected {span_id!r}, found {stack[-1]!r}."
            )
        _span_stack.set(stack[:-1])

    @staticmethod
    def clear() -> None:
        _current_tracer.set(None)
        _span_stack.set(())
