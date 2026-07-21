"""Immutable facts emitted during an AI execution."""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)

from sentinelai.execution_stream.schemas import (
    EventMetadata,
    EventPayload,
    freeze_mapping,
    thaw_mapping,
)


class ExecutionEvent(BaseModel):
    """Base envelope for an append-only execution fact."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    execution_id: UUID
    payload: EventPayload = Field(default_factory=lambda: freeze_mapping(None))
    metadata: EventMetadata = Field(default_factory=lambda: freeze_mapping(None))

    @field_validator("payload", "metadata", mode="after")
    @classmethod
    def _make_mapping_immutable(cls, value: EventPayload) -> EventPayload:
        return freeze_mapping(value)

    @field_serializer("payload", "metadata")
    def _serialize_mapping(self, value: EventPayload) -> dict[str, Any]:
        return thaw_mapping(value)

    def payload_dict(self) -> dict[str, Any]:
        """Return a mutable, JSON-serializable copy of the frozen payload."""
        return thaw_mapping(self.payload)

    def metadata_dict(self) -> dict[str, Any]:
        """Return a mutable, JSON-serializable copy of the frozen metadata."""
        return thaw_mapping(self.metadata)


class ExecutionStarted(ExecutionEvent):
    event_type: Literal["execution.started"] = "execution.started"


class ExecutionCompleted(ExecutionEvent):
    event_type: Literal["execution.completed"] = "execution.completed"


class ExecutionFailed(ExecutionEvent):
    event_type: Literal["execution.failed"] = "execution.failed"


class ExecutionCancelled(ExecutionEvent):
    event_type: Literal["execution.cancelled"] = "execution.cancelled"


class TraceCreated(ExecutionEvent):
    event_type: Literal["trace.created"] = "trace.created"


class TraceCompleted(ExecutionEvent):
    event_type: Literal["trace.completed"] = "trace.completed"


class SpanStarted(ExecutionEvent):
    event_type: Literal["span.started"] = "span.started"


class SpanCompleted(ExecutionEvent):
    event_type: Literal["span.completed"] = "span.completed"


class VerificationCompleted(ExecutionEvent):
    event_type: Literal["verification.completed"] = "verification.completed"


class AnalysisCompleted(ExecutionEvent):
    event_type: Literal["analysis.completed"] = "analysis.completed"
