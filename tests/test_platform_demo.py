"""Public sandbox demo API behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from sentinelai.contracts import ExecutionSnapshot, ModelInfo, Trace
from sentinelai_platform.api import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_demo_is_public_and_retains_sandbox_execution() -> None:
    client = _client()

    created = client.post(
        "/api/v1/demo/query",
        json={"mode": "rag", "input": "Where is the handbook?"},
    )

    assert created.status_code == 200
    body = created.json()
    execution_id = body["execution_id"]
    assert body["mode"] == "rag"
    assert body["status"] == "completed"
    assert "Sandbox retrieval response" in body["answer"]

    snapshot = client.get(f"/api/v1/demo/executions/{execution_id}")
    assert snapshot.status_code == 200
    assert snapshot.json()["metadata"] == {
        "environment": "sandbox",
        "source": "public_demo",
        "execution_name": "public_demo",
    }

    trace = client.get(f"/api/v1/demo/executions/{execution_id}/trace")
    assert trace.status_code == 200
    assert [span["name"] for span in trace.json()["spans"]] == [
        "demo.query",
        "planner",
        "executor",
        "llm",
    ]


def test_demo_rate_limit_allows_five_requests_per_ip() -> None:
    client = _client()
    payload = {"mode": "chat", "input": "hello"}

    for _ in range(5):
        assert client.post("/api/v1/demo/query", json=payload).status_code == 200

    limited = client.post("/api/v1/demo/query", json=payload)
    assert limited.status_code == 429


def test_demo_uses_injected_runner_when_configured() -> None:
    app = create_app()

    async def _runner(payload: object) -> object:
        from datetime import UTC, datetime
        from uuid import uuid4

        from sentinelai.contracts import ExecutionSnapshot, ModelInfo, Trace
        from sentinelai_platform.api.demo import DemoQueryResult

        execution_id = uuid4()
        started = datetime.now(UTC)
        return DemoQueryResult(
            execution_id=execution_id,
            answer="Real pipeline answer",
            latency_ms=12.5,
            mode="rag",
            snapshot=ExecutionSnapshot(
                execution_id=execution_id,
                query="q",
                response={"answer": "Real pipeline answer"},
                model_info=ModelInfo(provider="test", model_name="test"),
                created_at=started,
                metadata={
                    "environment": "sandbox",
                    "source": "public_demo",
                    "execution_name": "public_demo",
                },
                execution_status="completed",
                intent="retrieval",
            ),
            trace=Trace(trace_id=str(uuid4()), started_at=started),
        )

    app.state.demo_query_runner = _runner
    client = TestClient(app)

    created = client.post(
        "/api/v1/demo/query",
        json={"mode": "rag", "input": "What is the refund window?"},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["answer"] == "Real pipeline answer"
    assert "Sandbox" not in body["answer"]


def test_demo_read_routes_hide_non_sandbox_records() -> None:
    app = create_app()
    execution_id = uuid4()
    app.state.demo_executions = {
        execution_id: {
            "snapshot": ExecutionSnapshot(
                execution_id=execution_id,
                query="private",
                response={"answer": "private"},
                model_info=ModelInfo(provider="test", model_name="test"),
                created_at=datetime.now(UTC),
                metadata={"environment": "production"},
                execution_status="completed",
            ),
            "trace": Trace(
                trace_id=str(uuid4()),
                started_at=datetime.now(UTC),
            ),
        }
    }
    client = TestClient(app)

    assert client.get(f"/api/v1/demo/executions/{execution_id}").status_code == 404
    assert client.get(f"/api/v1/demo/executions/{execution_id}/trace").status_code == 404
