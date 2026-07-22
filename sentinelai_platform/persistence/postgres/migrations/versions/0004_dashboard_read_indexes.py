"""Add indexes for Dashboard V1 execution list filters.

Revision ID: 0004_dashboard_read_indexes
Revises: 0003_document_ownership_note
Create Date: 2026-07-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_dashboard_read_indexes"
down_revision: str | None = "0003_document_ownership_note"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_execution_snapshots_status_created_at",
        "execution_snapshots",
        ["execution_status", "created_at"],
    )
    op.create_index(
        "ix_execution_snapshots_model_created_at",
        "execution_snapshots",
        ["model_name", "created_at"],
    )
    # Expression index for explorer filter on metadata.execution_name.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_execution_snapshots_execution_name "
        "ON execution_snapshots ((snapshot -> 'metadata' ->> 'execution_name'))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_execution_snapshots_execution_name")
    op.drop_index(
        "ix_execution_snapshots_model_created_at",
        table_name="execution_snapshots",
    )
    op.drop_index(
        "ix_execution_snapshots_status_created_at",
        table_name="execution_snapshots",
    )
