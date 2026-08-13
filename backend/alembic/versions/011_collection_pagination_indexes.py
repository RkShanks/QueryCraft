"""011 collection pagination indexes

Revision ID: 011
Revises: 010
Create Date: 2026-08-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_sessions_user_activity_page",
        "sessions",
        ["user_id", sa.text("last_activity_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_accepted_queries_session_user_accepted_page",
        "accepted_queries",
        [
            "session_id",
            "user_id",
            sa.text("accepted_at DESC"),
            sa.text("id DESC"),
        ],
    )
    op.create_index(
        "ix_users_role_id_page",
        "users",
        ["role_id", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_users_role_id_page", table_name="users")
    op.drop_index(
        "ix_accepted_queries_session_user_accepted_page",
        table_name="accepted_queries",
    )
    op.drop_index("ix_sessions_user_activity_page", table_name="sessions")
