"""Phase 6 quota schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RoleQuotaConfig(BaseModel):
    """Quota configuration for one role."""

    role_id: UUID
    role_name: str
    daily_query_limit: int | None = None
    daily_execution_limit: int | None = None
    daily_export_limit: int | None = None
    created_at: datetime
    updated_at: datetime


class RoleQuotaUpsert(BaseModel):
    """Create or update quota limits for one role."""

    daily_query_limit: int | None = Field(default=None, ge=0)
    daily_execution_limit: int | None = Field(default=None, ge=0)
    daily_export_limit: int | None = Field(default=None, ge=0)


class QuotaDimensionStatus(BaseModel):
    """Current usage for one quota dimension."""

    limit: int | None = None
    used: int
    remaining: int | None = None


class RoleQuotaStatus(BaseModel):
    """Current quota status for one role."""

    role_id: UUID
    role_name: str
    dimensions: dict[str, QuotaDimensionStatus]
    reset_at: datetime


class QuotaStatusResponse(BaseModel):
    """Quota status list response."""

    status: list[RoleQuotaStatus]


class QuotaListResponse(BaseModel):
    """Quota configuration list response."""

    quotas: list[RoleQuotaConfig]
