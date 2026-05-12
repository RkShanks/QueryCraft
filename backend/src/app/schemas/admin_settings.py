"""Admin settings Pydantic schemas."""

from pydantic import BaseModel, Field


class AdminSettingsResponse(BaseModel):
    """GET /admin/settings response."""

    llm_context_cap: int


class UpdateAdminSettingsRequest(BaseModel):
    """PATCH /admin/settings request body."""

    llm_context_cap: int = Field(..., ge=0, le=10)


class UpdateAdminSettingsResponse(BaseModel):
    """Response after updating admin settings."""

    llm_context_cap: int
    updated_at: str
