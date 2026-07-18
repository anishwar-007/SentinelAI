"""decouple platform tables from lifecycle ledger FKs

Revision ID: 0003_document_ownership_note
Revises: 0002_execution_snapshots
Create Date: 2026-07-18

Platform tables (execution_snapshots, traces, spans) are persisted by SentinelAI
Platform. The mutable ``executions`` lifecycle ledger and document tables remain
available for the reference runtime, but canonical rows no longer depend on the
lifecycle table via foreign keys.

Traces keep an ``execution_id`` column for correlation. Linking to
``execution_snapshots`` is enforced by application order (snapshot before
trace) where a snapshot exists; document-index flows may emit traces without a
snapshot, so a hard FK is not added.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_document_ownership_note"
down_revision: str | None = "0002_execution_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("traces_execution_id_fkey", "traces", type_="foreignkey")
    op.drop_constraint(
        "fk_execution_snapshots_execution_id",
        "execution_snapshots",
        type_="foreignkey",
    )


def downgrade() -> None:
    op.create_foreign_key(
        "fk_execution_snapshots_execution_id",
        "execution_snapshots",
        "executions",
        ["execution_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "traces_execution_id_fkey",
        "traces",
        "executions",
        ["execution_id"],
        ["id"],
        ondelete="CASCADE",
    )
