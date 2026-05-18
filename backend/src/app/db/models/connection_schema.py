"""ConnectionSchemaEntry ORM model for schema introspection results (FR-065, FR-066).

Table: connection_schema_entries
Lifecycle: Full-replace on refresh — all rows DELETEd then re-inserted.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConnectionSchemaEntry(Base):
    """Single column entry from schema introspection.

    Rows are fully replaced on each refresh (DELETE all + INSERT all).
    """

    __tablename__ = "connection_schema_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        "id",
        server_default=text("gen_random_uuid()"),
        primary_key=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        "connection_id",
        ForeignKey("source_database_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    table_name: Mapped[str] = mapped_column("table_name", String, nullable=False)
    column_name: Mapped[str] = mapped_column("column_name", String, nullable=False)
    column_data_type: Mapped[str] = mapped_column("column_data_type", String, nullable=False)
    is_primary_key: Mapped[bool] = mapped_column(
        "is_primary_key", Boolean, nullable=False, default=False, server_default=text("false")
    )
    foreign_key_table: Mapped[str | None] = mapped_column("foreign_key_table", String, nullable=True)
    foreign_key_column: Mapped[str | None] = mapped_column("foreign_key_column", String, nullable=True)
    introspected_at: Mapped[datetime] = mapped_column(
        "introspected_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        Index("ix_conn_schema_entries_conn_id", "connection_id"),
        UniqueConstraint("connection_id", "table_name", "column_name", name="uq_conn_schema_entry"),
    )
