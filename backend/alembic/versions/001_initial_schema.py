"""001 initial schema — creates users, database_connections, accepted_queries, app_config

Revision ID: 001
Revises: None
Create Date: 2026-05-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="admin"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    # Database connections table
    op.create_table(
        "database_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("host", sa.Text(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="5432"),
        sa.Column("database_name", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("encrypted_password", sa.Text(), nullable=False),
        sa.Column("ssl_mode", sa.Text(), nullable=False, server_default="require"),
        sa.Column("schema_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("schema_cached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Accepted queries table
    op.create_table(
        "accepted_queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("database_connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("generated_sql", sa.Text(), nullable=False),
        sa.Column("llm_provider", sa.Text(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["database_connection_id"], ["database_connections.id"]),
    )
    op.create_index(
        "idx_accepted_queries_user_id_accepted_at",
        "accepted_queries",
        ["user_id", sa.text("accepted_at DESC")],
    )

    # App config table
    op.create_table(
        "app_config",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("key"),
    )

    # Seed app_config defaults
    op.execute("""
        INSERT INTO app_config (key, value) VALUES
            ('query_timeout_seconds', '30'::jsonb),
            ('max_question_length', '2000'::jsonb),
            ('session_idle_timeout_hours', '8'::jsonb),
            ('schema_cache_ttl_seconds', '300'::jsonb),
            ('max_schema_tokens', '60000'::jsonb)
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("app_config")
    op.drop_index("idx_accepted_queries_user_id_accepted_at", table_name="accepted_queries")
    op.drop_table("accepted_queries")
    op.drop_table("database_connections")
    op.drop_table("users")
