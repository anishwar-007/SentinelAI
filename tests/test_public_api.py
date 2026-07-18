from __future__ import annotations

import sentinelai
from sentinelai import (
    ExecutionContext,
    ExecutionMetadata,
    ExecutionRepository,
    ExecutionSnapshot,
    ObservedResult,
    TraceRepository,
    configure,
    observe,
    observe_execution,
    record_metadata,
)
from sentinelai.tracing import trace_span


def test_public_exports_are_importable() -> None:
    assert observe is sentinelai.observe
    assert observe_execution is sentinelai.observe_execution
    assert configure is sentinelai.configure
    assert ExecutionMetadata is sentinelai.ExecutionMetadata
    assert ObservedResult is sentinelai.ObservedResult
    assert record_metadata is sentinelai.record_metadata
    assert ExecutionContext is sentinelai.ExecutionContext
    assert ExecutionSnapshot is sentinelai.ExecutionSnapshot
    assert ExecutionRepository is sentinelai.ExecutionRepository
    assert TraceRepository is sentinelai.TraceRepository


def test_observe_is_trace_span_alias() -> None:
    assert observe is trace_span


def test_adapters_are_not_top_level_exports() -> None:
    assert not hasattr(sentinelai, "PostgresTraceRepository")
    assert not hasattr(sentinelai, "SupabaseStorageProvider")
    assert not hasattr(sentinelai, "LocalStorageProvider")
