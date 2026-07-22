# SentinelAI Public API

## Frozen SDK surface

Customer instrumentation should use only:

```python
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
from sentinelai.execution_stream import InMemoryExecutionStream
```

Compatibility guarantees within this major version:

- `configure(...)` is called once in the composition root.
- `execution(...)` owns the execution lifecycle.
- `span(...)` owns span instrumentation and inferred stage capture.
- Ambient getters expose correlation IDs for HTTP/edge adapters.
- `Contracts` exposes protocol DTOs such as `ExecutionSnapshot`, `Trace`, and
  `ModelInfo`.
- `Plugin` is the framework extension point.
- Lifecycle objects such as `ExecutionContext`, `ObservedResult`,
  `record_metadata`, repository ports, and `TraceContext` are internal or
  compatibility-only and must not appear in customer business code.

## Execution Stream

```python
from sentinelai.execution_stream import (
    ExecutionCompleted,
    ExecutionEvent,
    ExecutionEventPublisher,
    ExecutionEventSubscriber,
    ExecutionStream,
    InMemoryExecutionStream,
)
```

Events are the primary domain facts. Platform subscribers project those facts
into Execution Views such as snapshots, lifecycle rows, and traces.

## Contracts

```python
from sentinelai import Contracts

Contracts.ExecutionSnapshot
Contracts.ModelInfo
Contracts.PromptReference
Contracts.Trace
Contracts.Span
```

Persistence DTOs such as lifecycle/trace rows belong to the Platform package.

## Optional Platform surface

```python
from sentinelai_platform.api import create_app, router
from sentinelai_platform.event_subscribers import register_persistence_subscribers
from sentinelai_platform.execution_store import TracePersister
from sentinelai_platform.ports.storage import StorageProvider
from sentinelai_platform.repositories import (
    ExecutionLifecycleRepository,
    ExecutionSnapshotRepository,
    TraceRepository,
)
```

## Dashboard HTTP APIs

Protected (Bearer Supabase JWT via `require_user`):

- `GET /api/v1/executions`
- `GET /api/v1/executions/{id}`
- `GET /api/v1/executions/{id}/trace`

Public:

- `GET /health`
- `POST /api/v1/demo/query` (rate-limited; input ≤ 500; sandbox by default;
  reference runtime injects the real orchestrator pipeline)
- `GET /api/v1/demo/executions/{id}` and `.../trace` (sandbox metadata only)

Auth env: `SUPABASE_URL` (required for JWKS / ES256 signing keys), optional
`SUPABASE_JWT_SECRET` (Legacy HS256 only). Local bypass only:
`SENTINELAI_AUTH_DISABLED=1` when neither is set. CORS via
`SENTINELAI_DASHBOARD_ORIGINS` (allows `Authorization`).

## Internal implementation

Do not depend on:

- `sentinelai.execution.context.ExecutionContext` from customer business code;
- repository ports inside `sentinelai.repositories`;
- Alembic internals as Python APIs;
- deprecated local `app.main` launcher from a published package.
