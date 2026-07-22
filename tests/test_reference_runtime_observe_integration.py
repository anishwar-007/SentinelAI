from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from examples.reference_runtime.analysis.schemas import ComponentConfidence, RootCauseAnalysis
from examples.reference_runtime.executor import ExecutionResult
from examples.reference_runtime.planner.schemas import Plan
from examples.reference_runtime.retriever.schemas import IndexedDocument
from examples.reference_runtime.schemas import LLMResponse
from examples.reference_runtime.services.orchestrator import AIOrchestrator, EmptyQueryError
from examples.reference_runtime.verifier.schemas import VerificationResult
from sentinelai import (
    configure,
    get_current_execution_id,
    get_current_trace_id,
    span,
)
from sentinelai.contracts import (
    ExecutionSnapshot,
    ExecutionSummary,
    ModelInfo,
    PromptReference,
    Trace,
)
from sentinelai.execution_stream import (
    ExecutionCompleted,
    ExecutionEvent,
    ExecutionStarted,
    InMemoryExecutionStream,
    TraceCompleted,
)
from sentinelai.sdk.configure import reset_configuration
from sentinelai_platform.event_subscribers import register_persistence_subscribers
from sentinelai_platform.projections import ExecutionRecord


class _MemoryLifecycle:
    def __init__(self) -> None:
        self.records: dict[UUID, ExecutionRecord] = {}

    async def create(self, record: ExecutionRecord) -> ExecutionRecord:
        self.records[record.id] = record
        return record

    async def update(self, record: ExecutionRecord) -> ExecutionRecord:
        self.records[record.id] = record
        return record


class _MemorySnapshots:
    def __init__(self) -> None:
        self.snapshots: dict[UUID, ExecutionSnapshot] = {}

    async def save(self, snapshot: ExecutionSnapshot) -> None:
        self.snapshots[snapshot.execution_id] = snapshot

    async def load(self, execution_id: UUID) -> ExecutionSnapshot | None:
        return self.snapshots.get(execution_id)

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
        execution_name: str | None = None,
        model: str | None = None,
        from_time: object | None = None,
        to_time: object | None = None,
    ) -> list[ExecutionSummary]:
        del status, execution_name, model, from_time, to_time
        values = list(self.snapshots.values())[offset : offset + limit]
        return [
            ExecutionSummary(
                execution_id=item.execution_id,
                query=item.query,
                intent=item.intent,
                trace_id=item.trace_id,
                model_name=item.model_info.model_name,
                execution_status=item.execution_status,
                repository_version=item.repository_version,
                created_at=item.created_at,
                execution_name=(
                    item.metadata.get("execution_name")
                    if isinstance(item.metadata.get("execution_name"), str)
                    else None
                ),
            )
            for item in values
        ]

    async def count(
        self,
        *,
        status: str | None = None,
        execution_name: str | None = None,
        model: str | None = None,
        from_time: object | None = None,
        to_time: object | None = None,
    ) -> int:
        del status, execution_name, model, from_time, to_time
        return len(self.snapshots)


class _MemoryTracePersister:
    def __init__(self) -> None:
        self.traces: dict[UUID, dict[str, object]] = {}

    async def persist(self, trace: Trace, execution_id: UUID) -> str:
        del execution_id
        self.traces[UUID(trace.trace_id)] = trace.model_dump(mode="json")
        return f"traces/{trace.trace_id}.json"

    async def load(self, trace_id: UUID) -> dict[str, object]:
        return self.traces[trace_id]


class _Planner:
    @span("planner")
    async def plan(self, user_query: str) -> Plan:
        return Plan(
            intent="chat",
            confidence=0.91,
            reasoning=f"chat for {user_query}",
        )


class _Executor:
    @span("executor")
    async def execute(self, plan: Plan, user_query: str) -> ExecutionResult:
        del plan
        return ExecutionResult(
            output=LLMResponse(
                request_id="req-1",
                model="test-model",
                response=f"answer:{user_query}",
                usage={"prompt_tokens": 1, "completion_tokens": 1},
                latency_ms=12.0,
            )
        )


class _Verifier:
    @span("verifier")
    async def verify(self, query: str, context: str, answer: str) -> VerificationResult:
        del context
        return VerificationResult(
            verdict="approved",
            confidence=0.8,
            summary=f"{query}:{answer}",
        )


class _Analyzer:
    @span("root_cause_analysis")
    async def analyze(self, **kwargs: Any) -> RootCauseAnalysis:
        del kwargs
        return RootCauseAnalysis(
            primary_component="executor",
            severity="low",
            confidence=0.7,
            summary="ok",
            recommendation="none",
            evidence=["span"],
            confidence_graph=[
                ComponentConfidence(
                    component="executor",
                    confidence=0.7,
                    reasoning="stable",
                )
            ],
        )


class _IndexOutcome(BaseModel):
    document: IndexedDocument
    deduplicated: bool = False


class _Retriever:
    class _Registry:
        async def list_documents(self) -> list[IndexedDocument]:
            return []

        async def get_document(self, document_id: UUID) -> IndexedDocument:
            raise KeyError(document_id)

    def __init__(self) -> None:
        self.registry = self._Registry()

    async def index_document(
        self,
        content: str,
        document_id: str | None = None,
        *,
        filename: str | None = None,
        source: str | None = None,
    ) -> _IndexOutcome:
        del content
        return _IndexOutcome(
            document=IndexedDocument(
                document_id=UUID(document_id) if document_id else uuid4(),
                filename=filename or source or "untitled.txt",
                content_hash="hash",
                indexed_at=datetime.now(UTC),
                chunk_count=1,
                embedding_model="test-embed",
                status="ready",
                metadata={},
            ),
            deduplicated=False,
        )


@pytest.fixture(autouse=True)
def _reset_sdk() -> None:
    reset_configuration()
    yield
    reset_configuration()


def _build_orchestrator() -> tuple[
    AIOrchestrator,
    _MemoryLifecycle,
    _MemorySnapshots,
    list[ExecutionEvent],
]:
    stream = InMemoryExecutionStream()
    events: list[ExecutionEvent] = []

    class Capture:
        async def handle(self, event: ExecutionEvent) -> None:
            events.append(event)

    stream.subscribe(ExecutionEvent, Capture())
    executions = _MemoryLifecycle()
    snapshots = _MemorySnapshots()
    traces = _MemoryTracePersister()
    register_persistence_subscribers(
        stream,
        executions=executions,  # type: ignore[arg-type]
        snapshots=snapshots,  # type: ignore[arg-type]
        trace_persister=traces,  # type: ignore[arg-type]
    )
    configure(
        publisher=stream,
        model_info=ModelInfo(provider="test", model_name="test-model"),
        prompt_catalog={
            "planner": PromptReference(
                prompt_id="planner.plan_user_query",
                version="v1",
                name="Query Planner",
                hash="1" * 64,
            ),
            "executor.chat": PromptReference(
                prompt_id="executor.chat",
                version="v1",
                name="Chat Completion",
                hash="2" * 64,
            ),
            "verifier": PromptReference(
                prompt_id="verifier.answer",
                version="v1",
                name="Answer Verification",
                hash="3" * 64,
            ),
            "analyzer": PromptReference(
                prompt_id="analyzer.root_cause",
                version="v1",
                name="Root Cause Analysis",
                hash="4" * 64,
            ),
        },
    )
    orchestrator = AIOrchestrator(
        planner=_Planner(),  # type: ignore[arg-type]
        executor=_Executor(),  # type: ignore[arg-type]
        retriever=_Retriever(),  # type: ignore[arg-type]
        verifier=_Verifier(),  # type: ignore[arg-type]
        analyzer=_Analyzer(),  # type: ignore[arg-type]
    )
    return orchestrator, executions, snapshots, events


@pytest.mark.asyncio
async def test_run_emits_events_and_persists_snapshot() -> None:
    orchestrator, executions, snapshots, events = _build_orchestrator()

    outcome = await orchestrator.run("What is the refund window?")
    execution_id = get_current_execution_id()
    assert execution_id is not None
    assert outcome.intent == "chat"
    assert outcome.result["response"] == "answer:What is the refund window?"
    assert get_current_trace_id() is not None
    assert isinstance(events[0], ExecutionStarted)
    assert any(isinstance(event, TraceCompleted) for event in events)
    assert isinstance(events[-1], ExecutionCompleted)
    assert events[-1].payload.get("snapshot") is None
    assert events[-1].payload.get("project_snapshot") is True

    record = executions.records[execution_id]
    assert record.status == "completed"
    snapshot = snapshots.snapshots[execution_id]
    assert snapshot.intent == "chat"
    assert snapshot.plan is not None
    assert snapshot.verification is not None
    assert snapshot.analysis is not None
    assert snapshot.metadata["verification_status"] == "ok"
    assert "planner" in snapshot.prompt_references
    assert "executor.chat" in snapshot.prompt_references


@pytest.mark.asyncio
async def test_index_document_omits_snapshot_but_updates_lifecycle() -> None:
    orchestrator, executions, snapshots, events = _build_orchestrator()

    outcome = await orchestrator.index_document(
        "policy text",
        filename="policy.txt",
    )
    execution_id = get_current_execution_id()
    assert execution_id is not None
    assert outcome.document.filename == "policy.txt"
    terminal = events[-1]
    assert isinstance(terminal, ExecutionCompleted)
    assert "snapshot" not in terminal.payload
    assert terminal.payload["intent"] == "document_index"
    assert execution_id in executions.records
    assert snapshots.snapshots == {}


@pytest.mark.asyncio
async def test_empty_query_does_not_start_execution() -> None:
    orchestrator, executions, _snapshots, events = _build_orchestrator()

    with pytest.raises(EmptyQueryError):
        await orchestrator.run("   ")

    assert events == []
    assert executions.records == {}
