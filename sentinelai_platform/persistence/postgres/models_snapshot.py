import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from sentinelai_platform.persistence.postgres.base import Base


class ExecutionSnapshotModel(Base):
    __tablename__ = "execution_snapshots"
    __table_args__ = (
        UniqueConstraint("trace_id", name="uq_execution_snapshots_trace_id"),
    )

    # Canonical immutable execution identity. No FK to the mutable lifecycle
    # ``executions`` table — that ledger is owned by the reference runtime.
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    trace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    repository_version: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    snapshot_data: Mapped[dict[str, Any]] = mapped_column(
        "snapshot",
        JSONB,
        nullable=False,
    )
