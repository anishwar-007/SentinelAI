"""Active execution ContextVar and declarative stage helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextvars import ContextVar, Token
from typing import Any

from sentinelai.contracts import PromptReference

_active_execution: ContextVar[Any] = ContextVar(
    "active_execution",
    default=None,
)

_STAGE_NAMES = frozenset(
    {
        "plan",
        "retrieval_result",
        "response",
        "verification",
        "analysis",
    }
)


def set_active_execution(context: Any) -> Token[Any]:
    return _active_execution.set(context)


def reset_active_execution(token: Token[Any]) -> None:
    _active_execution.reset(token)


def get_active_execution() -> Any | None:
    return _active_execution.get()


def record_metadata(**metadata: Any) -> None:
    """Attach metadata to the active execution, if one exists."""
    context = get_active_execution()
    if context is None:
        return
    context.metadata.update(metadata)


def apply_capture(
    context: Any,
    capture: str | Mapping[str, str],
    result: Any,
) -> None:
    """Record stage payloads from an observed function result."""
    if isinstance(capture, str):
        _set_known_stage(context, capture, result)
        return
    for stage, path in capture.items():
        _set_known_stage(context, stage, resolve_path(result, path))


def apply_prompt_keys(
    context: Any,
    prompt_keys: str | Sequence[str],
    catalog: Mapping[str, PromptReference],
) -> None:
    """Resolve prompt catalog keys into the active execution."""
    for key, reference in select_prompt_references(
        prompt_keys,
        catalog=catalog,
        intent=getattr(context, "intent", None),
    ).items():
        context.prompt_references[key] = reference


def select_prompt_references(
    prompt_keys: str | Sequence[str],
    *,
    catalog: Mapping[str, PromptReference],
    intent: str | None = None,
) -> dict[str, PromptReference]:
    keys = (prompt_keys,) if isinstance(prompt_keys, str) else tuple(prompt_keys)
    selected: dict[str, PromptReference] = {}
    for key in keys:
        resolved = key.format(intent=intent or "")
        reference = catalog.get(resolved)
        if reference is not None:
            selected[resolved] = reference
    return selected


def resolve_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if current is None:
            return None
        if isinstance(current, Mapping):
            current = current.get(part)
            continue
        current = getattr(current, part, None)
    return current


def _set_known_stage(context: Any, stage: str, value: Any) -> None:
    if stage not in _STAGE_NAMES:
        raise ValueError(
            f"Unknown execution stage capture target: {stage!r}. "
            f"Expected one of {sorted(_STAGE_NAMES)}."
        )
    context.set_stage(stage, value)


__all__ = [
    "apply_capture",
    "apply_prompt_keys",
    "get_active_execution",
    "record_metadata",
    "reset_active_execution",
    "resolve_path",
    "select_prompt_references",
    "set_active_execution",
]
