"""Shared FastAPI dependencies for Platform HTTP adapters."""

from fastapi import Request

from sentinelai_platform.execution_store.trace_persister import TracePersister
from sentinelai_platform.repositories.execution import ExecutionSnapshotRepository
from sentinelai_platform.repositories.trace import TraceRepository


def get_execution_repository(request: Request) -> ExecutionSnapshotRepository:
    repository = getattr(request.app.state, "execution_repository", None)
    if repository is None:
        raise RuntimeError(
            "ExecutionSnapshotRepository is not configured on app.state."
        )
    return repository  # type: ignore[no-any-return]


def get_trace_persister(request: Request) -> TracePersister:
    persister = getattr(request.app.state, "trace_persister", None)
    if persister is None:
        raise RuntimeError("TracePersister is not configured on app.state.")
    return persister  # type: ignore[no-any-return]


def get_trace_repository(request: Request) -> TraceRepository | None:
    """Optional; used to resolve traces when snapshot.trace_id is missing."""
    return getattr(request.app.state, "trace_repository", None)  # type: ignore[no-any-return]
