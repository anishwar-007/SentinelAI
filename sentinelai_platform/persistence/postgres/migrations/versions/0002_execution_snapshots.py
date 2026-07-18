"""add immutable execution snapshots

Revision ID: 0002_execution_snapshots
Revises: 0001_initial
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_execution_snapshots"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_snapshots",
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("execution_status", sa.String(length=32), nullable=False),
        sa.Column("repository_version", sa.String(length=32), nullable=False),
        sa.Column("model_name", sa.String(length=256), nullable=False),
        sa.Column("intent", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name="fk_execution_snapshots_execution_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("execution_id"),
        sa.UniqueConstraint(
            "trace_id",
            name="uq_execution_snapshots_trace_id",
        ),
    )
    op.create_index(
        "ix_execution_snapshots_created_at",
        "execution_snapshots",
        ["created_at"],
    )
    op.create_index(
        "ix_execution_snapshots_execution_status",
        "execution_snapshots",
        ["execution_status"],
    )
    op.create_index(
        "ix_execution_snapshots_intent",
        "execution_snapshots",
        ["intent"],
    )
    op.create_index(
        "ix_execution_snapshots_model_name",
        "execution_snapshots",
        ["model_name"],
    )
    op.create_index(
        "ix_execution_snapshots_query_hash",
        "execution_snapshots",
        ["query_hash"],
    )
    op.create_index(
        "ix_execution_snapshots_trace_id",
        "execution_snapshots",
        ["trace_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_execution_snapshots_trace_id",
        table_name="execution_snapshots",
    )
    op.drop_index(
        "ix_execution_snapshots_query_hash",
        table_name="execution_snapshots",
    )
    op.drop_index(
        "ix_execution_snapshots_model_name",
        table_name="execution_snapshots",
    )
    op.drop_index(
        "ix_execution_snapshots_intent",
        table_name="execution_snapshots",
    )
    op.drop_index(
        "ix_execution_snapshots_execution_status",
        table_name="execution_snapshots",
    )
    op.drop_index(
        "ix_execution_snapshots_created_at",
        table_name="execution_snapshots",
    )
    op.drop_table("execution_snapshots")
