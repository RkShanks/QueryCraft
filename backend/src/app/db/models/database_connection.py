"""SourceDatabaseConnection ORM model (Phase 3 renamed from DatabaseConnection)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus


class SourceDatabaseConnection(Base):
    """Configured source database connection (Phase 3).

    Table renamed from database_connections to source_database_connections.
    Columns name, schema_metadata, schema_cached_at removed.
    New columns: display_name, database_type, lifecycle_state, health_status,
    last_health_check_at, health_error_category, schema_introspection_status,
    schema_last_refreshed_at.
    """

    __tablename__ = "source_database_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        "id",
        server_default=text("gen_random_uuid()"),
        primary_key=True,
    )
    display_name: Mapped[str] = mapped_column("display_name", String, nullable=False)
    database_type: Mapped[DatabaseType] = mapped_column("database_type", Enum(DatabaseType, native_enum=False), nullable=False)
    host: Mapped[str] = mapped_column("host", String, nullable=False)
    port: Mapped[int] = mapped_column("port", Integer, nullable=False, server_default="5432")
    database_name: Mapped[str] = mapped_column("database_name", String, nullable=False)
    username: Mapped[str] = mapped_column("username", String, nullable=False)
    encrypted_password: Mapped[str] = mapped_column("encrypted_password", String, nullable=False)
    ssl_mode: Mapped[str] = mapped_column("ssl_mode", String, nullable=False, server_default="require")
    lifecycle_state: Mapped[LifecycleState] = mapped_column(
        "lifecycle_state", Enum(LifecycleState, native_enum=False), nullable=False, default=LifecycleState.ACTIVE, server_default=text("'active'")
    )
    health_status: Mapped[HealthStatus] = mapped_column(
        "health_status", Enum(HealthStatus, native_enum=False), nullable=False, default=HealthStatus.UNTESTED, server_default=text("'untested'")
    )
    last_health_check_at: Mapped[datetime | None] = mapped_column(
        "last_health_check_at", DateTime(timezone=True), nullable=True
    )
    health_error_category: Mapped[str | None] = mapped_column("health_error_category", String, nullable=True)
    schema_introspection_status: Mapped[SchemaIntrospectionStatus] = mapped_column(
        "schema_introspection_status",
        Enum(SchemaIntrospectionStatus, native_enum=False),
        nullable=False,
        default=SchemaIntrospectionStatus.NONE,
        server_default=text("'none'"),
    )
    schema_last_refreshed_at: Mapped[datetime | None] = mapped_column(
        "schema_last_refreshed_at", DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (Index("ix_source_db_connections_lifecycle_state", "lifecycle_state"),)
