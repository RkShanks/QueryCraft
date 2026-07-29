"""009_phase6_audit_search_indexes

Add B-tree indexes on audit_log_entries(action_type, actor_identity, outcome,
timestamp) and a GIN index on audit_log_entries(context) to support efficient
audit search queries introduced in Wave 18.3.

All indexes use IF NOT EXISTS for idempotency. ``action_type`` and
``timestamp`` already exist at revision 008 because migration 007 created
them, so downgrade() preserves those inherited indexes and removes only the
indexes introduced by this revision.

Revision ID: 009
Revises: 008
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # B-tree indexes for equality / range filters used by AuditSearchService
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_entries_action_type ON audit_log_entries (action_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_entries_actor_identity ON audit_log_entries (actor_identity)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_entries_outcome ON audit_log_entries (outcome)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_entries_timestamp ON audit_log_entries (timestamp)")
    # GIN index for JSONB context column (containment / key-exists queries)
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_entries_context_gin ON audit_log_entries USING gin (context)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_audit_log_entries_context_gin")
    op.execute("DROP INDEX IF EXISTS ix_audit_log_entries_outcome")
    op.execute("DROP INDEX IF EXISTS ix_audit_log_entries_actor_identity")
