"""Phase 6 audit search and export schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.db.models.enums import AuditActionType

MAX_AUDIT_SEARCH_PAGE = 2_147_483_647
AUDIT_FILTER_CONTEXT_DEFAULT_TTL_SECONDS = 900
AUDIT_FILTER_CONTEXT_MAX_TTL_SECONDS = 3600

AuditOutcome = Literal["success", "failure", "denied", "blocked", "flagged", "broken"]
AuditFilterText = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=512,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]
AuditFilterField = Literal[
    "start_date",
    "end_date",
    "action_type",
    "actor_identity",
    "outcome",
    "resource_type",
]


class AuditFilterParams(BaseModel):
    """Validated filters shared by audit search and export."""

    start_date: datetime | None = None
    end_date: datetime | None = None
    action_type: AuditActionType | None = None
    actor_identity: AuditFilterText | None = None
    outcome: AuditOutcome | None = None
    resource_type: AuditFilterText | None = None

    @field_validator("start_date", "end_date")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        """Normalize date filters to timezone-aware UTC values."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        """Reject inverted ranges before any database query is built."""
        if self.start_date is not None and self.end_date is not None and self.start_date > self.end_date:
            raise ValueError("start_date must be less than or equal to end_date")
        return self


class AuditSearchParams(AuditFilterParams):
    """Audit search query parameters."""

    page: int = Field(default=1, ge=1, le=MAX_AUDIT_SEARCH_PAGE)
    page_size: int = Field(default=50, ge=1, le=100)


class AuditFilterContextRequest(AuditFilterParams):
    """Validated filters to seal into a short-lived opaque context."""

    expires_in_seconds: int = Field(
        default=AUDIT_FILTER_CONTEXT_DEFAULT_TTL_SECONDS,
        ge=1,
        le=AUDIT_FILTER_CONTEXT_MAX_TTL_SECONDS,
    )


class AuditFilterContextResponse(BaseModel):
    """Value-safe metadata returned for an opaque filter context."""

    filter_context: str
    applied_fields: list[AuditFilterField]
    expires_at: datetime


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


class AuditExportRequest(AuditFilterParams):
    """Audit export request filters."""

    format: Literal["csv", "json"]
