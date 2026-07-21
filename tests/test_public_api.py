from __future__ import annotations

import sentinelai
from sentinelai import (
    Contracts,
    ExecutionStream,
    Plugin,
    Sentinel,
    configure,
    execution,
    get_current_execution_id,
    get_current_execution_latency_ms,
    get_current_trace_id,
    span,
)
from sentinelai.tracing import observe, trace_span


def test_public_exports_are_importable() -> None:
    assert configure is sentinelai.configure
    assert execution is sentinelai.execution
    assert span is sentinelai.span
    assert Sentinel is sentinelai.Sentinel
    assert Contracts is sentinelai.Contracts
    assert ExecutionStream is sentinelai.ExecutionStream
    assert Plugin is sentinelai.Plugin
    assert get_current_execution_id is sentinelai.get_current_execution_id
    assert get_current_trace_id is sentinelai.get_current_trace_id
    assert (
        get_current_execution_latency_ms
        is sentinelai.get_current_execution_latency_ms
    )


def test_frozen_surface_hides_lifecycle_management() -> None:
    assert "ExecutionContext" not in sentinelai.__all__
    assert "ObservedResult" not in sentinelai.__all__
    assert "record_metadata" not in sentinelai.__all__
    assert "ExecutionRepository" not in sentinelai.__all__
    assert "TraceRepository" not in sentinelai.__all__


def test_observe_is_trace_span_alias() -> None:
    assert observe is trace_span


def test_adapters_are_not_top_level_exports() -> None:
    assert not hasattr(sentinelai, "PostgresTraceRepository")
    assert not hasattr(sentinelai, "SupabaseStorageProvider")
    assert not hasattr(sentinelai, "LocalStorageProvider")
