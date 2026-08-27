"""Security contract for opaque audit filter contexts (CHUNK-28)."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

from app.schemas.audit_search import AuditFilterContextRequest
from app.services.audit_filter_context import AuditFilterContextBinding, AuditFilterContextService


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
