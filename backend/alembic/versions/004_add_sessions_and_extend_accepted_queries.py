"""004 add sessions and extend accepted_queries

Revision ID: 004
Revises: 003
Create Date: 2026-05-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sessions table
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("preview_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_sessions_user_id_last_activity",
        "sessions",
        ["user_id", sa.text("last_activity_at DESC")],
    )

    # Add columns to accepted_queries
    op.add_column(
        "accepted_queries",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "accepted_queries",
        sa.Column("saved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "accepted_queries",
        sa.Column("feedback", sa.SmallInteger(), nullable=True),
    )
    op.create_index(
        "ix_accepted_queries_session_id",
        "accepted_queries",
        ["session_id"],
    )
    op.create_foreign_key(
        "fk_accepted_queries_session_id",
        "accepted_queries",
        "sessions",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Seed llm_context_cap in app_config
    op.execute("""
        INSERT INTO app_config (key, value) VALUES
            ('llm_context_cap', '3'::jsonb)
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_constraint("fk_accepted_queries_session_id", "accepted_queries", type_="foreignkey")
    op.drop_index("ix_accepted_queries_session_id", table_name="accepted_queries")
    op.drop_column("accepted_queries", "feedback")
    op.drop_column("accepted_queries", "saved")
    op.drop_column("accepted_queries", "session_id")
    op.drop_index("ix_sessions_user_id_last_activity", table_name="sessions")
    op.drop_table("sessions")
