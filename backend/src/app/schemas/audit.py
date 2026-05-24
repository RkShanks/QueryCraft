"""Phase 5 Audit Pydantic schemas (T-628).

Response models for audit verification and status endpoints.
"""

from pydantic import BaseModel


class AuditVerifyResponse(BaseModel):
    """Result of an audit chain integrity verification."""

    verified: bool
    entries_checked: int
    first_break_at: int | None = None
    verified_at: str


class AuditStatusResponse(BaseModel):
    """Audit log status including last verification result."""

    total_entries: int
    last_verification: dict | None = None
