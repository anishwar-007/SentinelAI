from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CURRENT_REPOSITORY_VERSION = "1.0"

ExecutionStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
]
TerminalExecutionStatus = Literal["completed", "failed", "cancelled"]


class ModelInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    model_name: str
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    seed: int | None = None
    reasoning_enabled: bool = False


class PromptReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt_id: str
    version: str
    name: str
    hash: str


class ExecutionSnapshot(BaseModel):
    """Immutable, canonical record of one terminal AI execution.

    Stage payloads (plan, retrieval, verification, analysis, response) are
    runtime-agnostic JSON documents so any customer application can persist
    its own domain models without coupling the SDK to a specific architecture.
    """

    model_config = ConfigDict(frozen=True)

    execution_id: UUID
    query: str
    plan: dict[str, Any] | None = None
    retrieval_result: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    analysis: dict[str, Any] | None = None
    trace_id: UUID | None = None
    model_info: ModelInfo
    prompt_references: dict[str, PromptReference] = Field(default_factory=dict)
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    repository_version: str = CURRENT_REPOSITORY_VERSION
    execution_status: TerminalExecutionStatus
    intent: str | None = None


class ExecutionSummary(BaseModel):
    """Lightweight list projection for explorers and dashboards.

    ``created_at`` is the execution start time. Optional fields are filled when
    the Platform can project them efficiently (lifecycle join / snapshot metadata).
    """

    model_config = ConfigDict(frozen=True)

    execution_id: UUID
    query: str
    intent: str | None = None
    trace_id: UUID | None = None
    model_name: str
    execution_status: TerminalExecutionStatus
    repository_version: str
    created_at: datetime
    execution_name: str | None = None
    latency_ms: float | None = None
    completed_at: datetime | None = None


class ExecutionRecord(BaseModel):
    """Mutable lifecycle DTO used by execution repository implementations."""

    id: UUID
    query: str
    intent: str | None
    status: str
    latency_ms: float | None
    created_at: datetime
    completed_at: datetime | None


class SnapshotCreationMetrics(BaseModel):
    """Timing and size metadata emitted when a snapshot is published."""

    serialization_latency_ms: float
    repository_latency_ms: float
    snapshot_size_bytes: int

    @property
    def publication_latency_ms(self) -> float:
        """Publication latency under the legacy-compatible metrics schema."""
        return self.repository_latency_ms
