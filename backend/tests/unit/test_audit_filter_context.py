"""Security contract for opaque audit filter contexts (CHUNK-28)."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.core.encryption import decrypt, encrypt
from app.schemas.audit_search import AuditFilterContextRequest
from app.services.audit_filter_context import (
    AuditFilterContextBinding,
    AuditFilterContextError,
    AuditFilterContextService,
)


def test_issued_context_round_trips_without_exposing_filter_values(test_encryption_key: str):
    issued_at = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
    canary = "actor-sensitive-canary"
    request = AuditFilterContextRequest(
        actor_identity=canary,
        resource_type="database-sensitive-canary",
        expires_in_seconds=300,
    )
    binding = AuditFilterContextBinding(user_id="user-a", session_id="session-a")
    service = AuditFilterContextService(test_encryption_key)

    issued = service.issue(request, binding, now=issued_at)

    assert set(issued.model_dump()) == {"filter_context", "applied_fields", "expires_at"}
    assert issued.applied_fields == ["actor_identity", "resource_type"]
    assert issued.expires_at == issued_at + timedelta(seconds=300)
    assert canary not in base64.b64decode(issued.filter_context).decode("utf-8", errors="ignore")

    resolved = service.resolve(
        issued.filter_context,
        binding,
        now=issued_at + timedelta(seconds=1),
    )
    assert resolved.actor_identity == canary
    assert resolved.resource_type == "database-sensitive-canary"


def test_expiry_metadata_matches_the_enforced_token_boundary(test_encryption_key: str):
    issued_at = datetime(2026, 8, 27, 12, 0, 0, 500_000, tzinfo=UTC)
    service = AuditFilterContextService(test_encryption_key)
    issued = service.issue(
        AuditFilterContextRequest(actor_identity="actor-a", expires_in_seconds=60),
        AuditFilterContextBinding(user_id="user-a", session_id="session-a"),
        now=issued_at,
    )

    service.resolve(
        issued.filter_context,
        AuditFilterContextBinding(user_id="user-a", session_id="session-a"),
        now=issued.expires_at - timedelta(microseconds=1),
    )


@pytest.mark.parametrize("expires_in_seconds", [0, -1, 3601])
def test_non_positive_or_excessive_expiry_is_rejected(expires_in_seconds: int):
    with pytest.raises(ValidationError):
        AuditFilterContextRequest(expires_in_seconds=expires_in_seconds)


def test_tampered_expired_and_wrong_identity_contexts_fail_closed(test_encryption_key: str):
    issued_at = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
    service = AuditFilterContextService(test_encryption_key)
    binding = AuditFilterContextBinding(user_id="user-a", session_id="session-a")
    issued = service.issue(
        AuditFilterContextRequest(actor_identity="actor-sensitive-canary", expires_in_seconds=60),
        binding,
        now=issued_at,
    )
    decoded = bytearray(base64.b64decode(issued.filter_context))
    decoded[-1] ^= 1
    invalid_cases = [
        (base64.b64encode(decoded).decode(), binding, issued_at),
        (issued.filter_context, binding, issued_at + timedelta(seconds=60)),
        (issued.filter_context, AuditFilterContextBinding("user-b", "session-a"), issued_at),
        (issued.filter_context, AuditFilterContextBinding("user-a", "session-b"), issued_at),
    ]

    for token, token_binding, current_time in invalid_cases:
        with pytest.raises(AuditFilterContextError) as exc_info:
            service.resolve(token, token_binding, now=current_time)
        assert str(exc_info.value) == ""


@pytest.mark.parametrize(
    ("field", "unsupported_value"),
    [("purpose", "different-purpose"), ("version", 2)],
)
def test_wrong_purpose_and_version_fail_with_the_same_error(
    test_encryption_key: str,
    field: str,
    unsupported_value: object,
):
    issued_at = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
    binding = AuditFilterContextBinding(user_id="user-a", session_id="session-a")
    service = AuditFilterContextService(test_encryption_key)
    issued = service.issue(AuditFilterContextRequest(actor_identity="actor-a"), binding, now=issued_at)
    payload = json.loads(decrypt(issued.filter_context, test_encryption_key))
    payload[field] = unsupported_value
    forged = encrypt(json.dumps(payload), test_encryption_key)

    with pytest.raises(AuditFilterContextError) as exc_info:
        service.resolve(forged, binding, now=issued_at)
    assert str(exc_info.value) == ""
