"""Admin settings Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class AdminSettingsResponse(BaseModel):
    """GET /admin/settings response."""

    llm_context_cap: int
    max_regenerate_attempts: int


class UpdateAdminSettingsRequest(BaseModel):
    """PATCH /admin/settings request body."""

    llm_context_cap: int = Field(..., ge=0, le=10)
    max_regenerate_attempts: int = Field(default=3, ge=1, le=10)


class UpdateAdminSettingsResponse(BaseModel):
    """Response after updating admin settings."""

    llm_context_cap: int
    max_regenerate_attempts: int
    updated_at: str


class SchemaRefreshResponse(BaseModel):
    """Schema introspection statistics returned by refresh operations."""

    tables_count: int
    columns_count: int
    refreshed_at: datetime
    approximate_tokens: int | None = None
