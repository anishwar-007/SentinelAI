# SentinelAI

SentinelAI is an AI Execution Intelligence system with three package
boundaries: a dependency-light SDK, an optional Platform backend, and a
reference runtime that behaves like a customer application.

## Install

```bash
# Core SDK (Pydantic only)
uv add sentinelai

# Optional Platform backend (API + persistence + storage)
uv add "sentinelai[platform]"

# This repository / reference runtime
uv sync --extra reference --extra dev
```

## Minimal instrumentation

```python
from sentinelai import configure, observe, observe_execution
from sentinelai.contracts import ModelInfo
from sentinelai.execution_stream import InMemoryExecutionStream

configure(
    publisher=InMemoryExecutionStream(),
    model_info=ModelInfo(provider="acme", model_name="demo"),
)

@observe("my_stage", capture="response")
async def run_stage(query: str) -> dict[str, str]:
    return {"answer": "ok"}

@observe_execution(execution_name="query")
async def main(query: str) -> dict[str, str]:
    return await run_stage(query)
```

Customer code describes what happened. The SDK owns execution lifecycle,
tracing, snapshot assembly, and execution-stream publication.

Use the optional Platform to project those facts into persistence:

```python
from sentinelai_platform.event_subscribers import register_persistence_subscribers
from sentinelai_platform.execution_store import TracePersister
from sentinelai_platform.persistence.postgres import (
    PostgresExecutionSnapshotRepository,
)
```

The SDK never imports `sentinelai_platform`, FastAPI, SQLAlchemy, Supabase, or
the reference runtime.

## Public API

Primary convenience exports from `sentinelai`:

- `configure`
- `observe_execution`
- `observe`
- `ExecutionMetadata`
- `ObservedResult`
- `ExecutionSnapshot`
- `ExecutionStream` / `InMemoryExecutionStream`

`ExecutionContext` and repository protocols remain importable for this major
version as compatibility surfaces. New integrations should not use them.

See [docs/public-api.md](docs/public-api.md) and
[docs/architecture.md](docs/architecture.md).

Contracts are available from `sentinelai.contracts`; stream APIs are under
`sentinelai.execution_stream`; plugin authors target `sentinelai.plugins.Plugin`.

Replay, evaluation, analytics, and dashboard namespaces are reserved under
`sentinelai_platform`; no engines or dashboard are implemented yet.

## Reference runtime

`examples/reference_runtime` is a demo customer application. It consumes the
SDK and opts into Platform persistence/API packages. It is **not** part of the
installable wheel.

```bash
cp .env.example .env
uv sync --extra reference --extra dev
uv run alembic upgrade head
uv run uvicorn examples.reference_runtime.main:app --reload
```

Seed sample documents (server must be running):

```bash
uv run python examples/reference_runtime/scripts/seed_sample_documents.py
```

Deprecated compatibility launcher (one release):

```bash
uv run uvicorn app.main:app --reload
```

Canonical command:

```bash
uv run uvicorn examples.reference_runtime.main:app --reload
```

## Migrations

- Reference deployment (this repo): `alembic.ini` →
  `examples/reference_runtime/db/migrations` (registers demo document models;
  uses the shared Platform revision chain).
- Platform-only installs: point Alembic at
  `sentinelai_platform/persistence/postgres/migrations`.

Do not rewrite applied revision history. Stamp/upgrade paths are documented in
[docs/architecture.md](docs/architecture.md).

## Development checks

```bash
uv run ruff check .
uv run mypy
uv run pytest
uv run alembic upgrade head
uv run alembic check
```
