from __future__ import annotations

import importlib

import pytest


def _route_paths(routes: list[object]) -> set[str]:
    paths: set[str] = set()
    for route in routes:
        path = getattr(route, "path", None)
        if isinstance(path, str):
            paths.add(path)
        nested = getattr(route, "routes", None)
        if nested is None:
            original_router = getattr(route, "original_router", None)
            nested = getattr(original_router, "routes", None)
        if isinstance(nested, list):
            paths.update(_route_paths(nested))
    return paths


def test_postgres_adapter_importable() -> None:
    module = importlib.import_module("sentinelai_platform.persistence.postgres")
    assert hasattr(module, "PostgresExecutionSnapshotRepository")
    assert hasattr(module, "PostgresTraceRepository")
    assert hasattr(module, "PostgresExecutionLifecycleRepository")


def test_storage_adapters_importable() -> None:
    local = importlib.import_module("sentinelai_platform.storage.local_provider")
    supabase = importlib.import_module("sentinelai_platform.storage.supabase_provider")
    provider = importlib.import_module("sentinelai_platform.ports.storage")
    assert hasattr(local, "LocalStorageProvider")
    assert hasattr(supabase, "SupabaseStorageProvider")
    assert hasattr(provider, "StorageProvider")


def test_api_adapter_requires_fastapi_extra() -> None:
    try:
        module = importlib.import_module("sentinelai_platform.api")
    except ModuleNotFoundError as exc:
        pytest.skip(f"api extra not installed: {exc}")
    assert hasattr(module, "create_app")
    assert hasattr(module, "router")
    paths = _route_paths(module.router.routes)
    assert "/health" in paths
    assert "/executions" in paths
    assert "/query" not in paths
    assert "/documents" not in paths


def test_plugin_protocol_is_documented_extension_point() -> None:
    module = importlib.import_module("sentinelai.plugins")
    assert hasattr(module, "Plugin")
