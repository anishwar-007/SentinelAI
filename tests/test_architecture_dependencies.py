"""Enforce SDK <- Platform / Runtime dependency direction."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENTINELAI = ROOT / "sentinelai"
PLATFORM = ROOT / "sentinelai_platform"

SDK_FORBIDDEN_ROOTS = {
    "alembic",
    "examples",
    "app",
    "asyncpg",
    "dashboard",
    "dotenv",
    "fastapi",
    "sentinelai_platform",
    "sqlalchemy",
    "supabase",
    "storage3",
    "qdrant_client",
    "sentence_transformers",
    "httpx",
    "uvicorn",
}

PLATFORM_FORBIDDEN_ROOTS = {"examples", "app"}


def _iter_python_files(package: Path) -> list[Path]:
    return list(package.rglob("*.py"))


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_sentinelai_source_avoids_forbidden_dependencies() -> None:
    violations: list[str] = []
    for path in _iter_python_files(SENTINELAI):
        for root in sorted(_imported_roots(path) & SDK_FORBIDDEN_ROOTS):
            violations.append(f"{path.relative_to(ROOT)} imports {root}")
    assert violations == [], "\n".join(violations)


def test_execution_telemetry_path_does_not_import_repositories() -> None:
    telemetry_files = [
        SENTINELAI / "execution" / "context.py",
        SENTINELAI / "execution" / "active.py",
        SENTINELAI / "sdk" / "configure.py",
        SENTINELAI / "sdk" / "metadata.py",
        SENTINELAI / "sdk" / "observe_execution.py",
        SENTINELAI / "tracing" / "decorators.py",
        *_iter_python_files(SENTINELAI / "execution_stream"),
    ]
    violations = [
        str(path.relative_to(ROOT))
        for path in telemetry_files
        if any(
            module.startswith("sentinelai.repositories")
            for module in _imported_modules(path)
        )
    ]
    assert violations == []


def test_execution_stream_has_no_platform_or_persistence_dependencies() -> None:
    allowed_sentinelai_prefix = "sentinelai.execution_stream"
    violations: list[str] = []
    for path in _iter_python_files(SENTINELAI / "execution_stream"):
        for module in _imported_modules(path):
            if module.startswith("sentinelai.") and not module.startswith(
                allowed_sentinelai_prefix
            ):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")
    assert violations == [], "\n".join(violations)


def test_platform_does_not_import_reference_runtime() -> None:
    violations: list[str] = []
    for path in _iter_python_files(PLATFORM):
        for root in sorted(_imported_roots(path) & PLATFORM_FORBIDDEN_ROOTS):
            violations.append(f"{path.relative_to(ROOT)} imports {root}")
    assert violations == [], "\n".join(violations)


def test_contracts_do_not_own_reference_business_models() -> None:
    contract_names = {
        node.name
        for path in _iter_python_files(SENTINELAI / "contracts")
        for node in ast.walk(
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        )
        if isinstance(node, ast.ClassDef)
    }
    assert contract_names.isdisjoint(
        {"VerificationResult", "RootCauseAnalysis", "PipelineSnapshot"}
    )


def test_sentinelai_package_imports_cleanly() -> None:
    import sys

    modules_before = set(sys.modules)
    import sentinelai

    assert sentinelai.__version__ == "2.0.0"
    assert not any(
        name == "sentinelai_platform" or name.startswith("sentinelai_platform.")
        for name in set(sys.modules) - modules_before
    )
    assert set(sentinelai.__all__) == {
        "ExecutionContext",
        "ExecutionMetadata",
        "ExecutionRepository",
        "ExecutionSnapshot",
        "ExecutionStream",
        "InMemoryExecutionStream",
        "InstrumentationSettings",
        "ModelInfo",
        "ObservedResult",
        "PromptReference",
        "TraceRepository",
        "configure",
        "get_active_execution",
        "get_settings",
        "observe",
        "observe_execution",
        "prompt_reference",
        "record_metadata",
        "reset_configuration",
    }
