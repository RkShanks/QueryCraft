"""009_phase6_audit_search_indexes

Add B-tree indexes on audit_log_entries(action_type, actor_identity, outcome,
timestamp) and a GIN index on audit_log_entries(context) to support efficient
audit search queries introduced in Wave 18.3.

All indexes use IF NOT EXISTS for idempotency. downgrade() drops them in
reverse order.

Revision ID: 009
Revises: 008
Create Date: 2026-06-23
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # B-tree indexes for equality / range filters used by AuditSearchService
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_log_entries_action_type "
        "ON audit_log_entries (action_type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_log_entries_actor_identity "
        "ON audit_log_entries (actor_identity)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_log_entries_outcome "
        "ON audit_log_entries (outcome)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_log_entries_timestamp "
        "ON audit_log_entries (timestamp)"
    )
    # GIN index for JSONB context column (containment / key-exists queries)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_log_entries_context_gin "
        "ON audit_log_entries USING gin (context)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_audit_log_entries_context_gin")
    op.execute("DROP INDEX IF EXISTS ix_audit_log_entries_timestamp")
    op.execute("DROP INDEX IF EXISTS ix_audit_log_entries_outcome")
    op.execute("DROP INDEX IF EXISTS ix_audit_log_entries_actor_identity")
    op.execute("DROP INDEX IF EXISTS ix_audit_log_entries_action_type")
