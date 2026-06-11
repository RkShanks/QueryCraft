"""Phase 6 audit search and export schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AuditSearchParams(BaseModel):
    """Audit search query parameters."""

    start_date: datetime | None = None
    end_date: datetime | None = None
    action_type: str | None = None
    actor_identity: str | None = None
    outcome: str | None = None
    resource_type: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)


class AuditEntryRead(BaseModel):
    """Search result representation of one audit entry."""

    sequence_number: int
    timestamp: datetime
    actor_identity: str | None = None
    action_type: str
    resource_type: str | None = None
    resource_id: str | None = None
    outcome: str
    context: dict


class AuditSearchPagination(BaseModel):
    """Audit search pagination metadata."""

    page: int
    page_size: int
    total_entries: int
    total_pages: int


class AuditSearchResponse(BaseModel):
    """Audit search response."""

    entries: list[AuditEntryRead]
    pagination: AuditSearchPagination


class AuditExportRequest(BaseModel):
    """Audit export request filters."""

    format: Literal["csv", "json"]
    start_date: datetime | None = None
    end_date: datetime | None = None
    action_type: str | None = None
    actor_identity: str | None = None
    outcome: str | None = None
    resource_type: str | None = None
