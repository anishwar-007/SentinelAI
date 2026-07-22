from __future__ import annotations

import importlib


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


def test_reference_runtime_modules_import() -> None:
    main = importlib.import_module("examples.reference_runtime.main")
    orchestrator = importlib.import_module(
        "examples.reference_runtime.services.orchestrator"
    )
    assert hasattr(main, "app")
    assert hasattr(orchestrator, "AIOrchestrator")
    paths = _route_paths(main.app.routes)
    assert {
        "/health",
        "/query",
        "/documents",
        "/executions",
        "/executions/{execution_id}",
        "/trace/{trace_id}",
        "/api/v1/executions",
        "/api/v1/executions/{execution_id}",
        "/api/v1/executions/{execution_id}/trace",
    } <= paths


def test_deprecated_app_main_shim() -> None:
    shim = importlib.import_module("app.main")
    reference = importlib.import_module("examples.reference_runtime.main")
    assert shim.app is reference.app
