"""Legacy unversioned Platform read routes (kept for compatibility).

Prefer the versioned Dashboard APIs under ``/api/v1``.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request

from sentinelai.contracts import ExecutionSnapshot, ExecutionSummary
from sentinelai_platform.api.deps import get_execution_repository, get_trace_persister
from sentinelai_platform.api.errors import ExecutionNotFoundError, TraceNotFoundError

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/executions", response_model=list[ExecutionSummary])
async def list_executions(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ExecutionSummary]:
    repository = get_execution_repository(request)
    return await repository.list(limit=limit, offset=offset)


@router.get("/executions/{execution_id}", response_model=ExecutionSnapshot)
async def get_execution(
    execution_id: UUID,
    request: Request,
) -> ExecutionSnapshot:
    repository = get_execution_repository(request)
    snapshot = await repository.load(execution_id)
    if snapshot is None:
        raise ExecutionNotFoundError(f"Execution not found: {execution_id}")
    return snapshot


@router.get("/trace/{trace_id}")
async def get_trace(trace_id: str, request: Request) -> dict[str, Any]:
    persister = get_trace_persister(request)
    try:
        return await persister.load(UUID(trace_id))
    except (ValueError, FileNotFoundError) as exc:
        raise TraceNotFoundError(f"Trace not found: {trace_id}") from exc
