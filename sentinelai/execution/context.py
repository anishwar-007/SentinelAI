from __future__ import annotations

import hashlib
import inspect
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from sentinelai.contracts import (
    CURRENT_REPOSITORY_VERSION,
    ExecutionSnapshot,
    ExecutionStatus,
    ModelInfo,
    PromptReference,
    SnapshotCreationMetrics,
    TerminalExecutionStatus,
    Trace,
)
from sentinelai.execution_stream import (
    AnalysisCompleted,
    ExecutionCancelled,
    ExecutionCompleted,
    ExecutionEvent,
    ExecutionEventPublisher,
    ExecutionFailed,
    ExecutionStarted,
    SpanCompleted,
    SpanStarted,
    TraceCompleted,
    TraceCreated,
    VerificationCompleted,
)
from sentinelai.tracing.tracer import Tracer


class ExecutionContext(BaseModel):
    """Mutable runtime state for one AI execution.

    Customer applications accumulate stage payloads here, then freeze the
    context into an immutable :class:`ExecutionSnapshot` at a terminal status.
    """

    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)

    execution_id: UUID = Field(default_factory=uuid4)
    query: str
    plan: Any = None
    retrieval_result: Any = None
    response: Any = None
    verification: Any = None
    analysis: Any = None
    trace: Trace | None = None
    model_info: ModelInfo
    prompt_references: dict[str, PromptReference] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    execution_status: ExecutionStatus = "pending"
    intent: str | None = None
    repository_version: str = CURRENT_REPOSITORY_VERSION

    def set_stage(self, name: str, value: Any) -> None:
        if name == "plan":
            self.plan = value
            intent = _extract_intent(value)
            if intent is not None:
                self.intent = intent
            return
        if name == "retrieval_result":
            self.retrieval_result = value
            return
        if name == "response":
            self.response = value
            return
        if name == "verification":
            self.verification = value
            return
        if name == "analysis":
            self.analysis = value
            return
        raise ValueError(f"Unknown execution stage: {name}")

    def mark_running(self) -> None:
        self.execution_status = "running"

    def mark_completed(self) -> None:
        self.execution_status = "completed"

    def mark_failed(self, *, error: BaseException | None = None) -> None:
        self.execution_status = "failed"
        if error is not None:
            self.metadata["error_type"] = type(error).__name__
            self.metadata["error"] = str(error)

    def mark_cancelled(self, *, error: BaseException | None = None) -> None:
        self.execution_status = "cancelled"
        if error is not None:
            self.metadata["error_type"] = type(error).__name__

    def attach_trace(self, trace: Trace | None) -> None:
        self.trace = trace

    def to_snapshot(self) -> ExecutionSnapshot:
        if self.execution_status not in {"completed", "failed", "cancelled"}:
            raise ValueError(
                "ExecutionSnapshot can only be created from a terminal context."
            )
        status: TerminalExecutionStatus = self.execution_status
        return ExecutionSnapshot(
            execution_id=self.execution_id,
            query=self.query,
            plan=_to_jsonable(self.plan),
            retrieval_result=_to_jsonable(self.retrieval_result),
            response=_to_jsonable(self.response),
            verification=_to_jsonable(self.verification),
            analysis=_to_jsonable(self.analysis),
            trace_id=UUID(self.trace.trace_id) if self.trace is not None else None,
            model_info=self.model_info,
            prompt_references=dict(self.prompt_references),
            created_at=self.created_at,
            metadata=dict(self.metadata),
            repository_version=self.repository_version,
            execution_status=status,
            intent=self.intent or _extract_intent(self.plan),
        )

    async def publish_started(
        self,
        publisher: ExecutionEventPublisher,
    ) -> None:
        """Publish the immutable fact that this execution has started."""
        await publisher.publish(
            ExecutionStarted(
                execution_id=self.execution_id,
                occurred_at=self.created_at,
                payload={
                    "query": self.query,
                    "intent": self.intent,
                    "model_info": self.model_info.model_dump(mode="json"),
                    "created_at": self.created_at,
                },
                metadata=self.metadata,
            )
        )

    async def publish_terminal(
        self,
        publisher: ExecutionEventPublisher,
        *,
        include_snapshot: bool = True,
    ) -> tuple[ExecutionSnapshot | None, SnapshotCreationMetrics]:
        """Publish all completed telemetry and the terminal execution fact."""
        serialization_started = time.perf_counter()
        snapshot = self.to_snapshot() if include_snapshot else None
        serialized = snapshot.model_dump_json() if snapshot is not None else "{}"
        serialization_latency_ms = (time.perf_counter() - serialization_started) * 1000

        events = self._terminal_events(snapshot)
        publication_started = time.perf_counter()
        for event in events:
            await publisher.publish(event)
        publication_latency_ms = (time.perf_counter() - publication_started) * 1000

        metrics = SnapshotCreationMetrics(
            serialization_latency_ms=serialization_latency_ms,
            repository_latency_ms=publication_latency_ms,
            snapshot_size_bytes=len(serialized.encode("utf-8")),
        )
        return snapshot, metrics

    async def persist(
        self,
        publisher: ExecutionEventPublisher,
    ) -> tuple[ExecutionSnapshot, SnapshotCreationMetrics]:
        """Compatibility alias for terminal event publication.

        This method no longer persists data. Pass an execution event publisher.
        """
        snapshot, metrics = await self.publish_terminal(publisher)
        if snapshot is None:
            raise RuntimeError("Terminal snapshot publication produced no snapshot.")
        return snapshot, metrics

    def _terminal_events(
        self,
        snapshot: ExecutionSnapshot | None,
    ) -> list[ExecutionEvent]:
        events: list[ExecutionEvent] = []
        if self.trace is not None:
            trace_data = self.trace.model_dump(mode="json")
            events.append(
                TraceCreated(
                    execution_id=self.execution_id,
                    occurred_at=self.trace.started_at,
                    payload={
                        "trace_id": self.trace.trace_id,
                        "started_at": self.trace.started_at,
                        "metadata": self.trace.metadata,
                    },
                    metadata=self.metadata,
                )
            )
            for span in self.trace.spans:
                span_data = span.model_dump(mode="json")
                events.append(
                    SpanStarted(
                        execution_id=self.execution_id,
                        occurred_at=span.start_time,
                        payload={
                            "trace_id": self.trace.trace_id,
                            "span_id": span.id,
                            "name": span.name,
                            "parent_span_id": span.parent_span_id,
                            "started_at": span.start_time,
                            "input": span.input,
                            "model": span.model,
                        },
                        metadata=self.metadata,
                    )
                )
                if span.end_time is not None:
                    events.append(
                        SpanCompleted(
                            execution_id=self.execution_id,
                            occurred_at=span.end_time,
                            payload={
                                "trace_id": self.trace.trace_id,
                                "span": span_data,
                            },
                            metadata=self.metadata,
                        )
                    )
            events.append(
                TraceCompleted(
                    execution_id=self.execution_id,
                    occurred_at=self.trace.ended_at or datetime.now(UTC),
                    payload={
                        "trace_id": self.trace.trace_id,
                        "trace": trace_data,
                    },
                    metadata=self.metadata,
                )
            )

        if self.verification is not None:
            events.append(
                VerificationCompleted(
                    execution_id=self.execution_id,
                    payload={"verification": _to_jsonable(self.verification)},
                    metadata=self.metadata,
                )
            )
        if self.analysis is not None:
            events.append(
                AnalysisCompleted(
                    execution_id=self.execution_id,
                    payload={"analysis": _to_jsonable(self.analysis)},
                    metadata=self.metadata,
                )
            )

        terminal_payload: dict[str, Any] = {
            "query": self.query,
            "intent": self.intent,
            "status": self.execution_status,
            "latency_ms": (
                self.trace.total_latency_ms if self.trace is not None else None
            ),
            "created_at": self.created_at,
            "completed_at": datetime.now(UTC),
        }
        if snapshot is not None:
            terminal_payload["snapshot"] = snapshot.model_dump(mode="json")

        event_class: type[ExecutionEvent]
        if self.execution_status == "completed":
            event_class = ExecutionCompleted
        elif self.execution_status == "cancelled":
            event_class = ExecutionCancelled
        else:
            event_class = ExecutionFailed
        events.append(
            event_class(
                execution_id=self.execution_id,
                payload=terminal_payload,
                metadata=self.metadata,
            )
        )
        return events

    @contextmanager
    def tracing(self, metadata: dict[str, Any] | None = None) -> Iterator[Tracer]:
        tracer = Tracer()
        merged = {"execution_id": str(self.execution_id), "query": self.query}
        if metadata:
            merged.update(metadata)
        with tracer.trace(metadata=merged):
            try:
                yield tracer
            finally:
                self.attach_trace(tracer.current_trace)


def prompt_reference(
    *,
    prompt_id: str,
    version: str,
    name: str,
    source: Callable[..., object],
) -> PromptReference:
    """Build a stable provisional reference without storing prompt text."""
    source_hash = hashlib.sha256(
        inspect.getsource(source).encode("utf-8")
    ).hexdigest()
    return PromptReference(
        prompt_id=prompt_id,
        version=version,
        name=name,
        hash=source_hash,
    )


def _to_jsonable(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, BaseModel):
        data = value.model_dump(mode="json")
        return data if isinstance(data, dict) else {"value": data}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        data = value.model_dump(mode="json")
        return data if isinstance(data, dict) else {"value": data}
    return {"value": value}


def _extract_intent(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        intent = value.get("intent")
        return intent if isinstance(intent, str) else None
    intent = getattr(value, "intent", None)
    return intent if isinstance(intent, str) else None
