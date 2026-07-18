"""Public decorator that owns the SentinelAI execution lifecycle."""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, ParamSpec, TypeVar, cast

from sentinelai.contracts import TerminalExecutionStatus
from sentinelai.execution.active import (
    get_active_execution,
    record_metadata,
    reset_active_execution,
    select_prompt_references,
    set_active_execution,
)
from sentinelai.execution.context import ExecutionContext
from sentinelai.sdk.configure import get_settings
from sentinelai.sdk.metadata import ExecutionMetadata, ObservedResult

P = ParamSpec("P")
R = TypeVar("R")

logger = logging.getLogger("sentinelai.sdk")

QueryResolver = str | Callable[..., str]
MetadataResolver = Mapping[str, Any] | Callable[..., Mapping[str, Any]]


def observe_execution(
    *,
    execution_name: str,
    query_arg: str = "query",
    query: QueryResolver | None = None,
    intent: str | None = None,
    metadata: MetadataResolver | None = None,
    include_snapshot: bool = True,
    return_metadata: bool = False,
    prompt_keys: str | Sequence[str] | None = None,
    capture_result: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Observe one customer execution boundary.

    The decorated function should contain only business logic. SentinelAI creates
    the execution, starts tracing, publishes lifecycle events, and finalizes the
    terminal snapshot/events automatically.
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                return await _run_observed(
                    fn,
                    args,
                    kwargs,
                    execution_name=execution_name,
                    query_arg=query_arg,
                    query=query,
                    intent=intent,
                    metadata=metadata,
                    include_snapshot=include_snapshot,
                    return_metadata=return_metadata,
                    prompt_keys=prompt_keys,
                    capture_result=capture_result,
                )

            return cast(Callable[P, R], async_wrapper)

        @functools.wraps(fn)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            raise TypeError(
                "observe_execution currently supports async callables only. "
                f"Got synchronous function {fn.__qualname__!r}."
            )

        return cast(Callable[P, R], sync_wrapper)

    return decorator


async def _run_observed(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    execution_name: str,
    query_arg: str,
    query: QueryResolver | None,
    intent: str | None,
    metadata: MetadataResolver | None,
    include_snapshot: bool,
    return_metadata: bool,
    prompt_keys: str | Sequence[str] | None,
    capture_result: str | None,
) -> Any:
    settings = get_settings()
    bound = _bound_arguments(fn, args, kwargs)
    resolved_query = _resolve_query(bound, query_arg=query_arg, query=query)
    resolved_metadata = {
        "execution_name": execution_name,
        **_resolve_metadata(bound, metadata),
    }
    initial_prompts = (
        select_prompt_references(
            prompt_keys,
            catalog=settings.prompt_catalog,
            intent=intent,
        )
        if prompt_keys is not None
        else {}
    )

    context = ExecutionContext(
        query=resolved_query,
        model_info=settings.model_info,
        prompt_references=initial_prompts,
        created_at=datetime.now(UTC),
        execution_status="pending",
        intent=intent,
        metadata=resolved_metadata,
    )
    context.mark_running()

    token = set_active_execution(context)
    context_error: BaseException | None = None
    result: Any = None
    try:
        await context.publish_started(settings.publisher)
        with context.tracing(metadata=dict(resolved_metadata)):
            try:
                result = await fn(*args, **kwargs)
                if capture_result is not None:
                    context.set_stage(capture_result, result)
                if context.execution_status == "running":
                    context.mark_completed()
            except asyncio.CancelledError as exc:
                context.mark_cancelled(error=exc)
                context_error = exc
                raise
            except Exception as exc:
                context.mark_failed(error=exc)
                context_error = exc
                raise
    finally:
        try:
            await context.publish_terminal(
                settings.publisher,
                include_snapshot=include_snapshot,
            )
        except Exception:
            logger.exception(
                "Failed to publish terminal execution %s",
                context.execution_id,
            )
            if context_error is None:
                context.mark_failed()
                reset_active_execution(token)
                raise
        reset_active_execution(token)

    if return_metadata:
        return ObservedResult(value=result, metadata=_execution_metadata(context))
    return result


def _execution_metadata(context: ExecutionContext) -> ExecutionMetadata:
    status = context.execution_status
    terminal_status: TerminalExecutionStatus
    if status == "completed":
        terminal_status = "completed"
    elif status == "cancelled":
        terminal_status = "cancelled"
    else:
        terminal_status = "failed"
    trace = context.trace
    return ExecutionMetadata(
        execution_id=context.execution_id,
        trace_id=trace.trace_id if trace is not None else None,
        latency_ms=trace.total_latency_ms if trace is not None else None,
        execution_status=terminal_status,
        intent=context.intent,
    )


def _bound_arguments(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    try:
        signature = inspect.signature(fn)
        bound = signature.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        values = dict(bound.arguments)
    except TypeError:
        values = {"args": list(args), **kwargs}
    values.pop("self", None)
    values.pop("cls", None)
    return values


def _resolve_query(
    bound: Mapping[str, Any],
    *,
    query_arg: str,
    query: QueryResolver | None,
) -> str:
    if callable(query):
        return str(query(**bound))
    if isinstance(query, str):
        return query
    value = bound.get(query_arg)
    if not isinstance(value, str):
        raise TypeError(
            f"observe_execution expected string argument {query_arg!r}, "
            f"got {type(value).__name__}."
        )
    return value


def _resolve_metadata(
    bound: Mapping[str, Any],
    metadata: MetadataResolver | None,
) -> dict[str, Any]:
    if metadata is None:
        return {}
    if callable(metadata):
        resolved = metadata(**bound)
        return dict(resolved)
    return dict(metadata)


__all__ = [
    "get_active_execution",
    "observe_execution",
    "record_metadata",
]
