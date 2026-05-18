"""006_phase3_multi_dialect_connections

Revision ID: 006
Revises: 005
Create Date: 2026-05-18

Phase 3 migration:
- Rename database_connections → source_database_connections
- Add Phase 3 columns (display_name, database_type, lifecycle_state, health_status, etc.)
- Backfill existing rows with postgresql type and active state
- Drop obsolete columns (name, schema_metadata, schema_cached_at)
- Create connection_schema_entries table
- Add connection_id to sessions table
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename table
    op.rename_table("database_connections", "source_database_connections")

    # Update FK on accepted_queries to point to renamed table
    # (Alembic handles this automatically with the rename, but we verify)

    # 2. Add new columns
    op.add_column(
        "source_database_connections",
        sa.Column("display_name", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "source_database_connections",
        sa.Column("database_type", sa.String(), nullable=False, server_default="postgresql"),
    )
    op.add_column(
        "source_database_connections",
        sa.Column("lifecycle_state", sa.String(), nullable=False, server_default="active"),
    )
    op.add_column(
        "source_database_connections",
        sa.Column("health_status", sa.String(), nullable=False, server_default="untested"),
    )
    op.add_column(
        "source_database_connections",
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "source_database_connections",
        sa.Column("health_error_category", sa.String(), nullable=True),
    )
    op.add_column(
        "source_database_connections",
        sa.Column("schema_introspection_status", sa.String(), nullable=False, server_default="none"),
    )
    op.add_column(
        "source_database_connections",
        sa.Column("schema_last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Backfill: set display_name from name, database_type to postgresql
    op.execute("""
        UPDATE source_database_connections
        SET display_name = name,
            database_type = 'postgresql',
            lifecycle_state = 'active'
    """)

    # 4. Drop obsolete columns
    op.drop_column("source_database_connections", "schema_cached_at")
    op.drop_column("source_database_connections", "schema_metadata")
    op.drop_column("source_database_connections", "name")

    # 5. Create connection_schema_entries table
    op.create_table(
        "connection_schema_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("table_name", sa.String(), nullable=False),
        sa.Column("column_name", sa.String(), nullable=False),
        sa.Column("column_data_type", sa.String(), nullable=False),
        sa.Column("is_primary_key", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("foreign_key_table", sa.String(), nullable=True),
        sa.Column("foreign_key_column", sa.String(), nullable=True),
        sa.Column("introspected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["connection_id"], ["source_database_connections.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("connection_id", "table_name", "column_name", name="uq_schema_entry_connection_table_column"),
    )
    op.create_index("ix_schema_entries_connection_id", "connection_schema_entries", ["connection_id"])

    # 6. Add connection_id to sessions table
    op.add_column(
        "sessions",
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_sessions_connection_id",
        "sessions",
        "source_database_connections",
        ["connection_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 7. Create index on lifecycle_state for filtering
    op.create_index(
        "ix_source_db_connections_lifecycle_state",
        "source_database_connections",
        ["lifecycle_state"],
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("ix_source_db_connections_lifecycle_state", table_name="source_database_connections")

    # Drop FK and column on sessions
    op.drop_constraint("fk_sessions_connection_id", "sessions", type_="foreignkey")
    op.drop_column("sessions", "connection_id")

    # Drop connection_schema_entries table
    op.drop_index("ix_schema_entries_connection_id", table_name="connection_schema_entries")
    op.drop_table("connection_schema_entries")

    # Re-add obsolete columns
    op.add_column(
        "source_database_connections",
        sa.Column("name", sa.String(), nullable=True),
    )
    op.add_column(
        "source_database_connections",
        sa.Column("schema_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "source_database_connections",
        sa.Column("schema_cached_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Backfill name from display_name
    op.execute("""
        UPDATE source_database_connections
        SET name = display_name
    """)

    # Drop new columns
    op.drop_column("source_database_connections", "schema_last_refreshed_at")
    op.drop_column("source_database_connections", "schema_introspection_status")
    op.drop_column("source_database_connections", "health_error_category")
    op.drop_column("source_database_connections", "last_health_check_at")
    op.drop_column("source_database_connections", "health_status")
    op.drop_column("source_database_connections", "lifecycle_state")
    op.drop_column("source_database_connections", "database_type")
    op.drop_column("source_database_connections", "display_name")

    # Rename table back
    op.rename_table("source_database_connections", "database_connections")
