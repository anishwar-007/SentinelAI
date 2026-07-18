import functools
import inspect
import traceback
from collections.abc import Callable, Mapping, Sequence
from typing import Any, ParamSpec, TypeVar, cast

from pydantic import BaseModel

from sentinelai.contracts import SpanStatus
from sentinelai.execution.active import (
    apply_capture,
    apply_prompt_keys,
    get_active_execution,
)
from sentinelai.tracing.context import TraceContext
from sentinelai.tracing.tracer import Tracer

P = ParamSpec("P")
R = TypeVar("R")

_MAX_STRING_CHARS = 2000


def _truncate(value: str) -> str:
    if len(value) <= _MAX_STRING_CHARS:
        return value
    return f"{value[:_MAX_STRING_CHARS]}...[truncated]"


def _serialize_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, str):
        return _truncate(value)
    if isinstance(value, (int, float, bool, type(None))):
        return value
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    return repr(value)


def _capture_input(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any:
    try:
        signature = inspect.signature(fn)
        bound = signature.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        values = dict(bound.arguments)
    except TypeError:
        values = {"args": list(args), "kwargs": kwargs}

    values.pop("self", None)
    values.pop("cls", None)
    if not values:
        return None
    return _serialize_value(values)


def _capture_output(result: Any) -> tuple[Any, str | None, dict[str, Any] | None]:
    if isinstance(result, BaseModel):
        data = result.model_dump(mode="json")
        model = data.get("model") if isinstance(data.get("model"), str) else None
        tokens = data.get("usage") if isinstance(data.get("usage"), dict) else None
        if "response" in data and "request_id" in data:
            return (
                {
                    "request_id": data.get("request_id"),
                    "response": _truncate(str(data.get("response", ""))),
                    "latency_ms": data.get("latency_ms"),
                },
                model,
                tokens,
            )
        return data, model, tokens
    return _serialize_value(result), None, None


def _finalize_span(
    tracer: Tracer,
    span: Any,
    *,
    status: SpanStatus,
    result: Any = None,
    error: str | None = None,
) -> None:
    if status == "ok":
        output, model, tokens = _capture_output(result)
        tracer.end_span(
            span,
            output=output,
            model=model,
            tokens=tokens,
            status="ok",
        )
        return

    tracer.end_span(span, status="error", error=error)


def _record_execution_side_effects(
    *,
    capture: str | Mapping[str, str] | None,
    prompt_keys: str | Sequence[str] | None,
    result: Any,
) -> None:
    if capture is None and prompt_keys is None:
        return
    execution = get_active_execution()
    if execution is None:
        return
    if capture is not None:
        apply_capture(execution, capture, result)
    if prompt_keys is not None:
        from sentinelai.sdk.configure import get_settings

        try:
            catalog = get_settings().prompt_catalog
        except RuntimeError:
            return
        apply_prompt_keys(execution, prompt_keys, catalog=catalog)


def trace_span(
    name: str,
    *,
    capture: str | Mapping[str, str] | None = None,
    prompt_keys: str | Sequence[str] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                tracer = TraceContext.get_tracer()
                if tracer is None:
                    bare_result = await fn(*args, **kwargs)
                    _record_execution_side_effects(
                        capture=capture,
                        prompt_keys=prompt_keys,
                        result=bare_result,
                    )
                    return bare_result

                span = tracer.start_span(
                    name,
                    payload=_capture_input(fn, args, kwargs),
                )
                status: SpanStatus = "error"
                error: str | None = None
                result: Any = None
                try:
                    result = await fn(*args, **kwargs)
                    status = "ok"
                    _record_execution_side_effects(
                        capture=capture,
                        prompt_keys=prompt_keys,
                        result=result,
                    )
                    return result
                except BaseException:
                    error = traceback.format_exc()
                    raise
                finally:
                    _finalize_span(
                        tracer,
                        span,
                        status=status,
                        result=result,
                        error=error,
                    )

            return cast(Callable[P, R], async_wrapper)

        @functools.wraps(fn)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            tracer = TraceContext.get_tracer()
            if tracer is None:
                bare_result = fn(*args, **kwargs)
                _record_execution_side_effects(
                    capture=capture,
                    prompt_keys=prompt_keys,
                    result=bare_result,
                )
                return bare_result

            span = tracer.start_span(
                name,
                payload=_capture_input(fn, args, kwargs),
            )
            status: SpanStatus = "error"
            error: str | None = None
            result: Any = None
            try:
                result = fn(*args, **kwargs)
                status = "ok"
                _record_execution_side_effects(
                    capture=capture,
                    prompt_keys=prompt_keys,
                    result=result,
                )
                return result
            except BaseException:
                error = traceback.format_exc()
                raise
            finally:
                _finalize_span(
                    tracer,
                    span,
                    status=status,
                    result=result,
                    error=error,
                )

        return cast(Callable[P, R], sync_wrapper)

    return decorator
