# SentinelAI Public API

## SDK convenience surface

Customer instrumentation should prefer:

```python
from sentinelai import (
    ExecutionMetadata,
    ExecutionSnapshot,
    ObservedResult,
    configure,
    observe,
    observe_execution,
    record_metadata,
)
from sentinelai.execution_stream import InMemoryExecutionStream
```

Compatibility guarantees within a major version:

- `configure(...)` is called once in the application composition root with an
  execution-stream publisher, model info, and optional prompt catalog.
- `observe_execution` owns the execution lifecycle: start, tracing, failure,
  cancellation, snapshot assembly, and terminal event publication.
- `observe` remains the public span instrumentation decorator. Optional
  `capture=` and `prompt_keys=` declaratively record stage payloads and prompt
  references into the active execution.
- `trace_span` remains the compatibility alias for `observe`.
- `ExecutionMetadata` / `ObservedResult` are optional correlation envelopes for
  API boundaries that must return `execution_id` / `trace_id`.
- `ExecutionContext` remains importable for this major version but is an
  internal lifecycle engine. New customer code should not construct it or call
  `mark_*`, `set_stage`, `publish_started`, `publish_terminal`, or `persist`.
- `ExecutionRepository` and `TraceRepository` remain importable compatibility
  protocols. New SDK instrumentation must not depend on them.

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

All concrete event classes share `event_id`, `event_type`, `occurred_at`,
`execution_id`, immutable `payload`, and immutable `metadata`.

`InMemoryExecutionStream` is the only implementation. Transport-specific
implementations are intentionally absent.

## Contracts

Shared DTOs are imported explicitly from `sentinelai.contracts`:

```python
from sentinelai.contracts import (
    ExecutionSnapshot,
    ExecutionStatus,
    ExecutionSummary,
    ModelInfo,
    PromptReference,
    Span,
    Trace,
)
```

The compatibility modules `sentinelai.execution.schemas` and
`sentinelai.tracing.schemas` re-export these classes for the current major
version. New code should use `sentinelai.contracts`.

## SDK extension surfaces

```python
from sentinelai.plugins import Plugin
```

No LangGraph, CrewAI, OpenAI Agents SDK, PydanticAI, or LlamaIndex plugin is
implemented yet.

## Optional Platform surface

Platform dependencies are installed with `sentinelai[platform]`. Import
concrete implementations only from `sentinelai_platform`:

```python
from sentinelai_platform.api import create_app, router
from sentinelai_platform.event_subscribers import (
    register_persistence_subscribers,
)
from sentinelai_platform.execution_store import TracePersister
from sentinelai_platform.persistence.postgres import (
    PostgresExecutionLifecycleRepository,
    PostgresExecutionSnapshotRepository,
    PostgresTraceRepository,
    create_engine,
    create_session_factory,
)
from sentinelai_platform.storage import (
    LocalStorageProvider,
    SupabaseStorageProvider,
)
```

The following namespaces are reserved and intentionally empty:

- `sentinelai_platform.replay`
- `sentinelai_platform.evaluation`
- `sentinelai_platform.analytics`
- `sentinelai_platform.dashboard`

`StorageProvider`, `ExecutionRepository`, and `TraceRepository` remain in the
SDK only as major-version compatibility protocols. Their concrete
implementations and all active usage belong to Platform code.

## Internal implementation

Do not depend on:

- `sentinelai_platform.persistence.postgres.models_*`;
- Alembic environment or revision modules as Python APIs;
- private serializer and tracing helpers;
- `examples.*` or the deprecated local `app.main` launcher from a published
  package.

## Import migration

- `sentinelai.api` → `sentinelai_platform.api`
- `sentinelai.collector` → `sentinelai_platform.execution_store`
- `sentinelai.repositories.postgres` →
  `sentinelai_platform.persistence.postgres`
- `sentinelai.storage.local_provider` →
  `sentinelai_platform.storage.local_provider`
- `sentinelai.storage.supabase_provider` →
  `sentinelai_platform.storage.supabase_provider`
- `sentinelai.storage.provider` → `sentinelai.ports.storage`
- `sentinelai.integrations.InstrumentationAdapter` →
  `sentinelai.plugins.Plugin`

These concrete compatibility shims are intentionally not kept inside the SDK:
they would force the SDK import graph to depend on the Platform.
