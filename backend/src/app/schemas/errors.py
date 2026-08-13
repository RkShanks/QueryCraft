"""Sanitized API error envelopes exposed by the runtime contract."""

from typing import Any, Literal

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Constant, user-safe error response."""

    error: str
    message_key: str
    message_params: dict[str, Any] | None = None
    field: str | None = None


class ValidationErrorDetail(BaseModel):
    """One sanitized request-validation failure."""

    field: str
    message_key: str
    message_params: dict[str, Any] | None = None


class ValidationErrorResponse(BaseModel):
    """Sanitized request-validation response."""

    error: Literal["validation"]
    message_key: str
    details: list[ValidationErrorDetail]


class QuotaExceededErrorResponse(BaseModel):
    """Quota denial with a safe retry timestamp."""

    error: Literal["quota_exceeded"]
    message_key: str
    reset_at: str


class QuotaSyncPendingErrorResponse(BaseModel):
    """Durable quota mutation awaiting cache publication."""

    error: Literal["quota_sync_pending"]
    message_key: str
    mutation_applied: Literal[True]
