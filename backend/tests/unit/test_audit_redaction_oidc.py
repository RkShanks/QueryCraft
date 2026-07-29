"""Wave 17.5c F-002 — Central OIDC redaction token coverage (FR-143 / SC-061).

The central audit redaction policy previously omitted the OIDC token
names that ``SsoService._safe_audit_context`` already redacts. While
the SSO service pre-redacts at the call site, defence-in-depth requires
``AuditService.log`` to also recognize these keys under any nesting
depth before writing the immutable audit log.

This module adds coverage for the tokens: ``nonce``, ``state``,
``code``, ``access_token``, ``id_token``, ``refresh_token``,
``accesstoken``, ``idtoken``, ``refreshtoken``. It tests top-level,
nested, list-of-dict, and dict-in-list nesting paths.
"""

from __future__ import annotations

import pytest

from app.db.models.enums import AuditActionType
from app.services.audit_service import AuditService

# Tokens under test. Names mirror the SSO service set verbatim so
# the two layers cannot drift.
_OIDC_TOKENS: tuple[str, ...] = (
    "nonce",
    "state",
    "code",
    "access_token",
    "id_token",
    "refresh_token",
    "accesstoken",
    "idtoken",
    "refreshtoken",
)


@pytest.mark.asyncio
class TestAuditServiceLogRedactsOidcTokens:
    """``AuditService.log`` must scrub every OIDC token in the context."""

    @pytest.mark.parametrize("token", _OIDC_TOKENS)
    async def test_oidc_token_redacted_in_log(self, db_session, token):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.AUTH_SSO_VALIDATION,
            context={token: f"raw-{token}-value", "control": "ok"},
        )
        assert entry.context[token] == "[REDACTED]", (
            f"Token {token!r} not redacted by AuditService.log: got {entry.context[token]!r}"
        )
        assert entry.context["control"] == "ok"

    async def test_nested_oidc_tokens_in_dict(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.AUTH_SSO_VALIDATION,
            context={
                "oidc_response": {
                    "nonce": "n-123",
                    "state": "s-456",
                    "code": "c-789",
                    "access_token": "eyJ...",
                    "id_token": "eyJid...",
                    "refresh_token": "rt-321",
                }
            },
        )
        ctx = entry.context["oidc_response"]
        assert ctx["nonce"] == "[REDACTED]"
        assert ctx["state"] == "[REDACTED]"
        assert ctx["code"] == "[REDACTED]"
        assert ctx["access_token"] == "[REDACTED]"
        assert ctx["id_token"] == "[REDACTED]"
        assert ctx["refresh_token"] == "[REDACTED]"

    async def test_nested_oidc_tokens_in_list_of_dicts(self, db_session):
        # Mirrors the OIDC callback flow: a list of assertions / claims,
        # each containing tokens that must not leak.
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.AUTH_SSO_VALIDATION,
            context={
                "events": [
                    {"type": "nonce_received", "nonce": "n1"},
                    {"type": "state_received", "state": "s1"},
                    {"type": "code_exchanged", "code": "c1"},
                ]
            },
        )
        events = entry.context["events"]
        assert events[0]["nonce"] == "[REDACTED]"
        assert events[1]["state"] == "[REDACTED]"
        assert events[2]["code"] == "[REDACTED]"
        # Type is a safe key; should pass through.
        assert events[0]["type"] == "nonce_received"
        assert events[1]["type"] == "state_received"
        assert events[2]["type"] == "code_exchanged"

    async def test_oidc_token_at_depth_three_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.AUTH_SSO_VALIDATION,
            context={
                "outer": {
                    "middle": {
                        "nonce": "deep-nonce",
                        "name": "safe-name",
                    }
                }
            },
        )
        assert entry.context["outer"]["middle"]["nonce"] == "[REDACTED]"
        assert entry.context["outer"]["middle"]["name"] == "safe-name"
