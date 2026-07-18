from sentinelai_platform.persistence.postgres.base import Base
from sentinelai_platform.persistence.postgres.execution_lifecycle_repository import (
    PostgresExecutionLifecycleRepository,
)
from sentinelai_platform.persistence.postgres.execution_snapshot_repository import (
    PostgresExecutionSnapshotRepository,
)
from sentinelai_platform.persistence.postgres.session import (
    create_engine,
    create_session_factory,
    session_scope,
)
from sentinelai_platform.persistence.postgres.trace_repository import PostgresTraceRepository

# Compatibility alias used by the reference runtime.
PostgresExecutionRepository = PostgresExecutionLifecycleRepository

__all__ = [
    "Base",
    "PostgresExecutionLifecycleRepository",
    "PostgresExecutionRepository",
    "PostgresExecutionSnapshotRepository",
    "PostgresTraceRepository",
    "create_engine",
    "create_session_factory",
    "session_scope",
]
