"""Authenticated-encrypted, identity-bound audit filter contexts."""

from __future__ import annotations

import binascii
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from cryptography.exceptions import InvalidTag
from pydantic import AwareDatetime, BaseModel, ValidationError

from app.core.encryption import decrypt, encrypt
from app.schemas.audit_search import (
    AUDIT_FILTER_FIELDS,
    AuditFilterContextRequest,
    AuditFilterContextResponse,
    AuditFilterParams,
    applied_audit_filter_fields,
)

_CONTEXT_PURPOSE = "audit_filter_context"
_CONTEXT_VERSION = 1


@dataclass(frozen=True)
class AuditFilterContextBinding:
    """Authenticated identity and HTTP session bound to a filter context."""

    user_id: str
    session_id: str


class AuditFilterContextError(Exception):
    """A filter context failed authenticated validation."""


class AuditFilterContextPayload(BaseModel):
    """Encrypted filter-context payload."""

    purpose: Literal["audit_filter_context"]
    version: Literal[1]
    user_id: str
    session_id: str
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    filters: AuditFilterParams


class AuditFilterContextService:
    """Issue and resolve stateless AES-GCM audit filter contexts."""

    def __init__(self, encryption_key: str) -> None:
        self._encryption_key = encryption_key

    def issue(
        self,
        request: AuditFilterContextRequest,
        binding: AuditFilterContextBinding,
        *,
        now: datetime | None = None,
    ) -> AuditFilterContextResponse:
        """Seal normalized filters without echoing their values."""
        issued_at = _utc_now(now)
        expires_at = issued_at + timedelta(seconds=request.expires_in_seconds)
        filters = AuditFilterParams.model_validate(request.model_dump(include=set(AUDIT_FILTER_FIELDS)))
        payload = AuditFilterContextPayload(
            purpose=_CONTEXT_PURPOSE,
            version=_CONTEXT_VERSION,
            user_id=binding.user_id,
            session_id=binding.session_id,
            issued_at=issued_at,
            expires_at=expires_at,
            filters=filters,
        )
        token = encrypt(payload.model_dump_json(), self._encryption_key)
        return AuditFilterContextResponse(
            filter_context=token,
            applied_fields=applied_audit_filter_fields(filters),
            expires_at=expires_at,
        )

    def resolve(
        self,
        filter_context: str,
        binding: AuditFilterContextBinding,
        *,
        now: datetime | None = None,
    ) -> AuditFilterParams:
        """Resolve a valid context for its bound identity and session."""
        try:
            plaintext = decrypt(filter_context, self._encryption_key)
            payload = AuditFilterContextPayload.model_validate(json.loads(plaintext))
        except (binascii.Error, InvalidTag, UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError):
            raise AuditFilterContextError from None

        current_time = _utc_now(now)
        if (
            payload.user_id != binding.user_id
            or payload.session_id != binding.session_id
            or payload.issued_at > current_time
            or payload.expires_at <= payload.issued_at
            or current_time >= payload.expires_at
        ):
            raise AuditFilterContextError
        return payload.filters


def _utc_now(current: datetime | None) -> datetime:
    instant = current or datetime.now(UTC)
    if instant.tzinfo is None:
        return instant.replace(tzinfo=UTC)
    return instant.astimezone(UTC)
