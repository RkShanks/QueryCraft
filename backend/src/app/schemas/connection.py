"""Pydantic schemas for admin connection CRUD API (T-411, FR-059, FR-060)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus


class ConnectionCreate(BaseModel):
    """Request body for creating a new source database connection."""

    display_name: str = Field(..., min_length=1, max_length=255)
    database_type: DatabaseType
    host: str = Field(..., min_length=1)
    port: int = Field(..., ge=1, le=65535)
    database_name: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    ssl_mode: str = Field(default="require", min_length=1)


class ConnectionUpdate(BaseModel):
    """Request body for updating an existing connection."""

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    database_type: DatabaseType | None = None
    host: str | None = Field(default=None, min_length=1)
    port: int | None = Field(default=None, ge=1, le=65535)
    database_name: str | None = Field(default=None, min_length=1)
    username: str | None = Field(default=None, min_length=1)
    password: str | None = None  # null/omitted = keep existing
    ssl_mode: str | None = Field(default=None, min_length=1)


class ConnectionResponse(BaseModel):
    """Response body for connection details (password never included)."""

    id: UUID
    display_name: str
    database_type: DatabaseType
    host: str
    port: int
    database_name: str
    username: str
    ssl_mode: str
    lifecycle_state: LifecycleState
    health_status: HealthStatus
    last_health_check_at: datetime | None
    health_error_category: str | None
    schema_introspection_status: SchemaIntrospectionStatus
    schema_last_refreshed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectionTestResult(BaseModel):
    """Response body for connection test result."""

    status: str  # "healthy" or "unhealthy"
    latency_ms: float | None = None
    error_category: str | None = None
    message_key: str | None = None
    tested_at: datetime


class ConnectionListResponse(BaseModel):
    """Response body for listing connections."""

    connections: list[ConnectionResponse]
