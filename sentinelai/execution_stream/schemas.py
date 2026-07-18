"""Immutable value helpers for execution event envelopes."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

type EventPayload = Mapping[str, Any]
type EventMetadata = Mapping[str, Any]


def freeze_mapping(value: Mapping[str, Any] | None) -> EventPayload:
    """Return a deeply immutable view of an event mapping."""
    if value is None:
        return MappingProxyType({})
    return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})


def thaw_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Convert an immutable event mapping into JSON-serializable containers."""
    return {str(key): _thaw(item) for key, item in value.items()}


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return thaw_mapping(value)
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return [_thaw(item) for item in value]
    return value
