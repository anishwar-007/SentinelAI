"""Dashboard V1 Platform API readiness tests (read-only /api/v1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sentinelai.contracts import (
    ExecutionSnapshot,
    ExecutionSummary,
    ModelInfo,
    Trace,
)
from sentinelai.contracts.tracing import Span
from sentinelai_platform.api import create_app, parse_dashboard_origins
from sentinelai_platform.api.errors import InvalidFilterError
from sentinelai_platform.api.schemas import ExecutionListItem
from sentinelai_platform.api.trace_views import project_trace_view
from sentinelai_platform.api.v1 import _validate_list_filters
from sentinelai_platform.projections import TraceRecord


@pytest.fixture(autouse=True)
def disable_platform_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dashboard repository tests exercise API behavior, not JWT validation."""
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setenv("SENTINELAI_AUTH_DISABLED", "1")


def _snapshot(
    *,
    execution_id: UUID | None = None,
    query: str = "hello",
    status: str = "completed",
    model_name: str = "gemma",
    execution_name: str = "query",
    created_at: datetime | None = None,
    trace_id: UUID | None = None,
    intent: str | None = "chat",
    latency_ms: float | None = 12.5,
    completed_at: datetime | None = None,
) -> ExecutionSnapshot:
    started = created_at or datetime.now(UTC)
    tid = trace_id or uuid4()
    return ExecutionSnapshot(
        execution_id=execution_id or uuid4(),
        query=query,
        response={"response": "ok"},
        trace_id=tid,
        model_info=ModelInfo(provider="openrouter", model_name=model_name),
        created_at=started,
        metadata={"execution_name": execution_name},
        execution_status=status,  # type: ignore[arg-type]
        intent=intent,
    )


class MemorySnapshotRepository:
    def __init__(self, snapshots: list[ExecutionSnapshot] | None = None) -> None:
        self._snapshots = list(snapshots or [])
        self._latency: dict[UUID, float | None] = {}
        self._completed: dict[UUID, datetime | None] = {}

    def seed_timing(
        self,
        execution_id: UUID,
        *,
        latency_ms: float | None,
        completed_at: datetime | None,
    ) -> None:
        self._latency[execution_id] = latency_ms
        self._completed[execution_id] = completed_at

    async def save(self, snapshot: ExecutionSnapshot) -> ExecutionSnapshot:
        self._snapshots.append(snapshot)
        return snapshot

    async def load(self, execution_id: UUID) -> ExecutionSnapshot | None:
        return next(
            (item for item in self._snapshots if item.execution_id == execution_id),
            None,
        )

    def _matches(
        self,
        item: ExecutionSnapshot,
        *,
        status: str | None,
        execution_name: str | None,
        model: str | None,
        from_time: datetime | None,
        to_time: datetime | None,
    ) -> bool:
        if status is not None and item.execution_status != status:
            return False
        if model is not None and item.model_info.model_name != model:
            return False
        if from_time is not None and item.created_at < from_time:
            return False
        if to_time is not None and item.created_at > to_time:
            return False
        if execution_name is not None:
            name = item.metadata.get("execution_name")
            if name != execution_name:
                return False
        return True

    def _filtered(
        self,
        *,
        status: str | None = None,
        execution_name: str | None = None,
        model: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> list[ExecutionSnapshot]:
        matched = [
            item
            for item in self._snapshots
            if self._matches(
                item,
                status=status,
                execution_name=execution_name,
                model=model,
                from_time=from_time,
                to_time=to_time,
            )
        ]
        return sorted(matched, key=lambda item: item.created_at, reverse=True)

    def _to_summary(self, item: ExecutionSnapshot) -> ExecutionSummary:
        name = item.metadata.get("execution_name")
        return ExecutionSummary(
            execution_id=item.execution_id,
            query=item.query,
            intent=item.intent,
            trace_id=item.trace_id,
            model_name=item.model_info.model_name,
            execution_status=item.execution_status,
            repository_version=item.repository_version,
            created_at=item.created_at,
            execution_name=name if isinstance(name, str) else None,
            latency_ms=self._latency.get(item.execution_id),
            completed_at=self._completed.get(item.execution_id),
        )

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
        execution_name: str | None = None,
        model: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> list[ExecutionSummary]:
        filtered = self._filtered(
            status=status,
            execution_name=execution_name,
            model=model,
            from_time=from_time,
            to_time=to_time,
        )
        return [self._to_summary(item) for item in filtered[offset : offset + limit]]

    async def count(
        self,
        *,
        status: str | None = None,
        execution_name: str | None = None,
        model: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> int:
        return len(
            self._filtered(
                status=status,
                execution_name=execution_name,
                model=model,
                from_time=from_time,
                to_time=to_time,
            )
        )

    async def find_by_trace(self, trace_id: UUID) -> ExecutionSnapshot | None:
        return next(
            (item for item in self._snapshots if item.trace_id == trace_id),
            None,
        )

    async def find_by_query(
        self,
        query: str,
        *,
        limit: int = 100,
    ) -> list[ExecutionSummary]:
        return [
            self._to_summary(item)
            for item in self._snapshots
            if item.query == query
        ][:limit]


class MemoryTracePersister:
    def __init__(self) -> None:
        self.traces: dict[UUID, dict[str, Any]] = {}

    async def persist(self, trace: Trace, execution_id: UUID) -> str:
        self.traces[UUID(trace.trace_id)] = {
            **trace.model_dump(mode="json"),
            "execution_id": str(execution_id),
        }
        return f"traces/{trace.trace_id}.json"

    async def load(self, trace_id: UUID) -> dict[str, Any]:
        if trace_id not in self.traces:
            raise FileNotFoundError(str(trace_id))
        return self.traces[trace_id]


class MemoryTraceRepository:
    def __init__(self) -> None:
        self.records: dict[UUID, TraceRecord] = {}

    async def create(self, trace: TraceRecord, spans: list[object]) -> TraceRecord:
        del spans
        self.records[trace.trace_id] = trace
        return trace

    async def get(self, trace_id: UUID) -> TraceRecord | None:
        return self.records.get(trace_id)

    async def find_by_execution_id(self, execution_id: UUID) -> TraceRecord | None:
        matches = [
            record
            for record in self.records.values()
            if record.execution_id == execution_id
        ]
        if not matches:
            return None
        return sorted(matches, key=lambda item: item.created_at, reverse=True)[0]

    async def list_spans(self, trace_id: UUID) -> list[object]:
        del trace_id
        return []

    async def delete(self, trace_id: UUID) -> None:
        self.records.pop(trace_id, None)


def _build_client(
    *,
    snapshots: MemorySnapshotRepository,
    persister: MemoryTracePersister,
    traces: MemoryTraceRepository | None = None,
    origins: list[str] | None = None,
    raise_server_exceptions: bool = True,
) -> TestClient:
    app = create_app(dashboard_origins=origins or [])
    app.state.execution_repository = snapshots
    app.state.trace_persister = persister
    app.state.trace_repository = traces
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


@pytest.fixture
def seeded() -> tuple[
    MemorySnapshotRepository,
    MemoryTracePersister,
    MemoryTraceRepository,
    ExecutionSnapshot,
    Trace,
]:
    now = datetime.now(UTC)
    parent_id = str(uuid4())
    child_id = str(uuid4())
    trace_id = uuid4()
    execution_id = uuid4()
    snapshot = _snapshot(
        execution_id=execution_id,
        trace_id=trace_id,
        created_at=now - timedelta(minutes=5),
        execution_name="query",
        model_name="gemma-4",
    )
    older = _snapshot(
        created_at=now - timedelta(hours=2),
        execution_name="index_document",
        model_name="other",
        status="failed",
        query="index me",
    )
    snapshots = MemorySnapshotRepository([snapshot, older])
    snapshots.seed_timing(
        execution_id,
        latency_ms=42.0,
        completed_at=now - timedelta(minutes=4),
    )
    trace = Trace(
        trace_id=str(trace_id),
        started_at=now - timedelta(minutes=5),
        ended_at=now - timedelta(minutes=4),
        total_latency_ms=42.0,
        spans=[
            Span(
                id=parent_id,
                name="query",
                start_time=now - timedelta(minutes=5),
                end_time=now - timedelta(minutes=4),
                latency_ms=42.0,
                status="ok",
                input={"query": "hello"},
                output={"ok": True},
            ),
            Span(
                id=child_id,
                name="planner",
                parent_span_id=parent_id,
                start_time=now - timedelta(minutes=5),
                end_time=now - timedelta(minutes=5) + timedelta(seconds=1),
                latency_ms=1000.0,
                status="ok",
                model="gemma-4",
                tokens={"prompt_tokens": 10, "completion_tokens": 5},
            ),
        ],
        metadata={"source": "test"},
    )
    persister = MemoryTracePersister()
    persister.traces[trace_id] = trace.model_dump(mode="json")
    traces = MemoryTraceRepository()
    traces.records[trace_id] = TraceRecord(
        trace_id=trace_id,
        execution_id=execution_id,
        status="completed",
        span_count=2,
        latency_ms=42.0,
        storage_path=f"traces/{trace_id}.json",
        created_at=now - timedelta(minutes=5),
    )
    return snapshots, persister, traces, snapshot, trace


def test_list_executions_paginated(seeded: Any) -> None:
    snapshots, persister, traces, *_ = seeded
    client = _build_client(snapshots=snapshots, persister=persister, traces=traces)
    response = client.get("/api/v1/executions", params={"limit": 1, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert body["total"] == 2
    assert body["has_more"] is True
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["execution_name"] == "query"
    assert item["model"] == "gemma-4"
    assert item["status"] == "completed"
    assert item["latency_ms"] == 42.0
    assert "started_at" in item


def test_list_executions_filters(seeded: Any) -> None:
    snapshots, persister, traces, *_ = seeded
    client = _build_client(snapshots=snapshots, persister=persister, traces=traces)

    by_status = client.get("/api/v1/executions", params={"status": "failed"})
    assert by_status.status_code == 200
    assert by_status.json()["total"] == 1
    assert by_status.json()["items"][0]["status"] == "failed"

    by_name = client.get(
        "/api/v1/executions",
        params={"execution_name": "index_document"},
    )
    assert by_name.json()["total"] == 1

    by_model = client.get("/api/v1/executions", params={"model": "gemma-4"})
    assert by_model.json()["total"] == 1

    window = client.get(
        "/api/v1/executions",
        params={
            "from_time": (datetime.now(UTC) - timedelta(minutes=30)).isoformat(),
            "to_time": datetime.now(UTC).isoformat(),
        },
    )
    assert window.status_code == 200
    assert window.json()["total"] == 1


def test_invalid_filters_return_400(seeded: Any) -> None:
    snapshots, persister, traces, *_ = seeded
    client = _build_client(snapshots=snapshots, persister=persister, traces=traces)
    bad_status = client.get("/api/v1/executions", params={"status": "running"})
    assert bad_status.status_code == 400
    assert "Invalid status" in bad_status.json()["detail"]

    bad_range = client.get(
        "/api/v1/executions",
        params={
            "from_time": "2026-07-21T12:00:00Z",
            "to_time": "2026-07-21T11:00:00Z",
        },
    )
    assert bad_range.status_code == 400


def test_execution_detail_and_not_found(seeded: Any) -> None:
    snapshots, persister, traces, snapshot, _trace = seeded
    client = _build_client(snapshots=snapshots, persister=persister, traces=traces)

    ok = client.get(f"/api/v1/executions/{snapshot.execution_id}")
    assert ok.status_code == 200
    body = ok.json()
    assert body["execution_id"] == str(snapshot.execution_id)
    assert body["response"] == {"response": "ok"}
    assert body["model_info"]["model_name"] == "gemma-4"
    assert body["metadata"]["execution_name"] == "query"

    missing = client.get(f"/api/v1/executions/{uuid4()}")
    assert missing.status_code == 404
    assert "not found" in missing.json()["detail"].lower()


def test_execution_trace_and_parent_child(seeded: Any) -> None:
    snapshots, persister, traces, snapshot, _trace = seeded
    client = _build_client(snapshots=snapshots, persister=persister, traces=traces)

    response = client.get(f"/api/v1/executions/{snapshot.execution_id}/trace")
    assert response.status_code == 200
    body = response.json()
    assert body["execution_id"] == str(snapshot.execution_id)
    assert body["trace_id"] == str(snapshot.trace_id)
    assert body["total_latency_ms"] == 42.0
    assert len(body["spans"]) == 2
    parent = next(span for span in body["spans"] if span["name"] == "query")
    child = next(span for span in body["spans"] if span["name"] == "planner")
    assert child["parent_span_id"] == parent["span_id"]
    assert child["tokens"]["prompt_tokens"] == 10
    assert parent["input"] == {"query": "hello"}


def test_trace_not_found(seeded: Any) -> None:
    snapshots, persister, traces, snapshot, _trace = seeded
    # Snapshot exists but storage/trace missing.
    del persister.traces[snapshot.trace_id]  # type: ignore[index]
    client = _build_client(snapshots=snapshots, persister=persister, traces=traces)
    response = client.get(f"/api/v1/executions/{snapshot.execution_id}/trace")
    assert response.status_code == 404
    assert "trace" in response.json()["detail"].lower()


def test_cors_configuration(seeded: Any) -> None:
    snapshots, persister, traces, *_ = seeded
    assert parse_dashboard_origins("") == []
    assert parse_dashboard_origins("http://localhost:3000, https://dash.example") == [
        "http://localhost:3000",
        "https://dash.example",
    ]

    client = _build_client(
        snapshots=snapshots,
        persister=persister,
        traces=traces,
        origins=["http://localhost:3000"],
    )
    response = client.options(
        "/api/v1/executions",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in {200, 204}
    assert (
        response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    )

    denied = client.get(
        "/api/v1/executions",
        headers={"Origin": "http://evil.example"},
    )
    assert denied.headers.get("access-control-allow-origin") != "http://evil.example"


def test_platform_error_responses_do_not_leak_internals(seeded: Any) -> None:
    snapshots, persister, traces, *_ = seeded

    class BoomRepo(MemorySnapshotRepository):
        async def list(self, **kwargs: Any) -> list[ExecutionSummary]:  # type: ignore[override]
            raise RuntimeError("psycopg2: connection refused SECRET")

        async def count(self, **kwargs: Any) -> int:  # type: ignore[override]
            raise RuntimeError("psycopg2: connection refused SECRET")

    client = _build_client(
        snapshots=BoomRepo(snapshots._snapshots),
        persister=persister,
        traces=traces,
        raise_server_exceptions=False,
    )
    response = client.get("/api/v1/executions")
    assert response.status_code == 500
    assert response.json()["detail"] == "Unexpected Platform error."
    assert "psycopg2" not in response.text
    assert "SECRET" not in response.text


def test_list_item_projection_and_filter_helpers() -> None:
    summary = ExecutionSummary(
        execution_id=uuid4(),
        query="q",
        intent="chat",
        trace_id=uuid4(),
        model_name="m",
        execution_status="completed",
        repository_version="1.0",
        created_at=datetime.now(UTC),
        execution_name="query",
        latency_ms=1.0,
        completed_at=datetime.now(UTC),
    )
    item = ExecutionListItem.from_summary(summary)
    assert item.model == "m"
    assert item.status == "completed"
    assert item.started_at == summary.created_at

    with pytest.raises(InvalidFilterError):
        _validate_list_filters(
            status="nope",
            from_time=None,
            to_time=None,
        )


def test_project_trace_preserves_parent_links() -> None:
    parent = str(uuid4())
    child = str(uuid4())
    execution_id = uuid4()
    view = project_trace_view(
        {
            "trace_id": str(uuid4()),
            "started_at": datetime.now(UTC).isoformat(),
            "ended_at": datetime.now(UTC).isoformat(),
            "total_latency_ms": 9.0,
            "spans": [
                {
                    "id": parent,
                    "name": "root",
                    "start_time": datetime.now(UTC).isoformat(),
                    "status": "ok",
                },
                {
                    "id": child,
                    "parent_span_id": parent,
                    "name": "child",
                    "start_time": datetime.now(UTC).isoformat(),
                    "status": "ok",
                    "tokens": {"prompt_tokens": 1},
                },
            ],
        },
        execution_id=execution_id,
    )
    assert view.spans[1].parent_span_id == parent
    assert view.spans[1].span_id == child


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


def test_create_app_registers_v1_routes() -> None:
    app: FastAPI = create_app()
    paths = _route_paths(app.routes)
    assert "/api/v1/executions" in paths
    assert "/api/v1/executions/{execution_id}" in paths
    assert "/api/v1/executions/{execution_id}/trace" in paths
    assert "/health" in paths
