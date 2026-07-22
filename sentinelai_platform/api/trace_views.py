"""Helpers for loading and projecting traces for Platform HTTP APIs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sentinelai.contracts import Trace
from sentinelai_platform.api.errors import TraceNotFoundError
from sentinelai_platform.api.schemas import ExecutionTraceView, SpanView
from sentinelai_platform.execution_store.trace_persister import TracePersister
from sentinelai_platform.repositories.execution import ExecutionSnapshotRepository
from sentinelai_platform.repositories.trace import TraceRepository


async def resolve_trace_id_for_execution(
    execution_id: UUID,
    *,
    snapshots: ExecutionSnapshotRepository,
    traces: TraceRepository | None,
) -> UUID:
    """Resolve the trace UUID for an execution from snapshot or trace ledger."""
    snapshot = await snapshots.load(execution_id)
    if snapshot is not None and snapshot.trace_id is not None:
        return snapshot.trace_id

    if traces is not None:
        record = await traces.find_by_execution_id(execution_id)
        if record is not None:
            return record.trace_id

    raise TraceNotFoundError(f"Trace not found for execution: {execution_id}")


async def load_execution_trace(
    execution_id: UUID,
    *,
    snapshots: ExecutionSnapshotRepository,
    persister: TracePersister,
    traces: TraceRepository | None = None,
) -> ExecutionTraceView:
    trace_id = await resolve_trace_id_for_execution(
        execution_id,
        snapshots=snapshots,
        traces=traces,
    )
    try:
        raw = await persister.load(trace_id)
    except FileNotFoundError as exc:
        raise TraceNotFoundError(f"Trace not found for execution: {execution_id}") from exc

    return project_trace_view(raw, execution_id=execution_id)


def project_trace_view(
    raw: dict[str, Any] | Trace,
    *,
    execution_id: UUID,
) -> ExecutionTraceView:
    """Map stored Trace JSON / contract into the Dashboard API view."""
    if isinstance(raw, Trace):
        data = raw.model_dump(mode="json")
        started_at = raw.started_at
        completed_at = raw.ended_at
        total_latency_ms = raw.total_latency_ms
        metadata = dict(raw.metadata)
        spans_raw = [span.model_dump(mode="json") for span in raw.spans]
        trace_id = raw.trace_id
    else:
        data = raw
        started_at = data.get("started_at")
        completed_at = data.get("ended_at")
        total_latency_ms = data.get("total_latency_ms")
        metadata_raw = data.get("metadata") or {}
        metadata = dict(metadata_raw) if isinstance(metadata_raw, dict) else {}
        spans_raw = data.get("spans") or []
        if not isinstance(spans_raw, list):
            spans_raw = []
        trace_id = str(data.get("trace_id", ""))

    spans = [_project_span(item) for item in spans_raw if isinstance(item, dict)]
    return ExecutionTraceView(
        trace_id=trace_id,
        execution_id=execution_id,
        started_at=started_at,
        completed_at=completed_at,
        total_latency_ms=total_latency_ms,
        spans=spans,
        metadata=metadata,
    )


def _project_span(raw: dict[str, Any]) -> SpanView:
    attributes_raw = raw.get("attributes")
    attributes = dict(attributes_raw) if isinstance(attributes_raw, dict) else {}
    tokens_raw = raw.get("tokens")
    tokens = dict(tokens_raw) if isinstance(tokens_raw, dict) else None
    return SpanView(
        span_id=str(raw.get("id") or raw.get("span_id") or ""),
        parent_span_id=(
            str(raw["parent_span_id"])
            if raw.get("parent_span_id") is not None
            else None
        ),
        name=str(raw.get("name") or ""),
        status=str(raw.get("status") or "running"),
        started_at=raw.get("start_time") or raw.get("started_at"),
        ended_at=raw.get("end_time") or raw.get("ended_at"),
        latency_ms=raw.get("latency_ms"),
        input=raw.get("input"),
        output=raw.get("output"),
        model=raw.get("model"),
        tokens=tokens,
        error=raw.get("error"),
        attributes=attributes,
    )
