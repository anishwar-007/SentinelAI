"""Dashboard V1 Platform read APIs under /api/v1."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from sentinelai.contracts import ExecutionSnapshot
from sentinelai_platform.api.auth import require_user
from sentinelai_platform.api.deps import (
    get_execution_repository,
    get_trace_persister,
    get_trace_repository,
)
from sentinelai_platform.api.errors import ExecutionNotFoundError, InvalidFilterError
from sentinelai_platform.api.schemas import (
    ExecutionListItem,
    ExecutionTraceView,
    PaginatedExecutions,
)
from sentinelai_platform.api.trace_views import load_execution_trace

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_user)])

_VALID_STATUSES = frozenset({"completed", "failed", "cancelled"})


@router.get("/executions", response_model=PaginatedExecutions)
async def list_executions(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    execution_name: str | None = Query(default=None, min_length=1, max_length=256),
    model: str | None = Query(default=None, min_length=1, max_length=256),
    from_time: datetime | None = Query(default=None),
    to_time: datetime | None = Query(default=None),
) -> PaginatedExecutions:
    _validate_list_filters(status=status, from_time=from_time, to_time=to_time)
    repository = get_execution_repository(request)
    filters = {
        "status": status,
        "execution_name": execution_name,
        "model": model,
        "from_time": from_time,
        "to_time": to_time,
    }
    total = await repository.count(**filters)
    summaries = await repository.list(limit=limit, offset=offset, **filters)
    items = [ExecutionListItem.from_summary(item) for item in summaries]
    has_more = offset + len(items) < total
    return PaginatedExecutions(
        items=items,
        limit=limit,
        offset=offset,
        total=total,
        has_more=has_more,
    )


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


@router.get(
    "/executions/{execution_id}/trace",
    response_model=ExecutionTraceView,
)
async def get_execution_trace(
    execution_id: UUID,
    request: Request,
) -> ExecutionTraceView:
    repository = get_execution_repository(request)
    # Ensure the execution exists before resolving a dangling trace id.
    snapshot = await repository.load(execution_id)
    if snapshot is None:
        raise ExecutionNotFoundError(f"Execution not found: {execution_id}")

    return await load_execution_trace(
        execution_id,
        snapshots=repository,
        persister=get_trace_persister(request),
        traces=get_trace_repository(request),
    )


def _validate_list_filters(
    *,
    status: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> None:
    if status is not None and status not in _VALID_STATUSES:
        raise InvalidFilterError(
            f"Invalid status filter: {status!r}. "
            f"Expected one of: {', '.join(sorted(_VALID_STATUSES))}."
        )
    if from_time is not None and to_time is not None and from_time > to_time:
        raise InvalidFilterError("from_time must be less than or equal to to_time.")


__all__ = ["router"]
