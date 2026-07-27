"""Regression coverage for fail-closed SSO identity collisions."""

from __future__ import annotations

import json
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType, AuthProvider
from app.db.models.role import Role
from app.db.models.sso_group_mapping import SsoGroupMapping
from app.db.models.sso_provider import SsoProvider
from app.db.models.user import User
from app.db.models.user_identity import UserIdentity
from app.services.sso_service import SsoService, SsoValidationError


def _oidc_provider() -> SsoProvider:
    return SsoProvider(
        id=uuid4(),
        protocol="oidc",
        display_name="Collision test OIDC",
        issuer_url="https://identity.example.test",
        client_id="collision-client",
        redirect_uri="https://app.example.test/api/v1/auth/sso/oidc/callback",
        group_claim_name="groups",
    )


async def _roles_and_mapping(db: AsyncSession) -> tuple[Role, Role, str]:
    suffix = uuid4().hex
    priority_base = 1_000_000 + uuid4().int % 1_000_000
    existing_role = Role(
        name=f"Existing identity {suffix}",
        priority=priority_base,
        permissions=["query.history.view"],
        is_builtin=False,
    )
    incoming_role = Role(
        name=f"Incoming identity {suffix}",
        priority=priority_base + 1,
        permissions=["query.submit"],
        is_builtin=False,
    )
    db.add_all([existing_role, incoming_role])
    await db.flush()

    group = f"collision-group-{suffix}"
    db.add(SsoGroupMapping(sso_group_value=group, role_id=incoming_role.id))
    await db.flush()
    return existing_role, incoming_role, group


async def _seed_identity(
    db: AsyncSession,
    *,
    role: Role,
    provider: AuthProvider,
    subject_id: str,
    email: str,
) -> tuple[User, UserIdentity]:
    user = User(
        username=email,
        display_name=email,
        password_hash=None,
        role="viewer",
        role_id=role.id,
        is_builtin=False,
        auth_provider=str(provider),
    )
    db.add(user)
    await db.flush()

    identity = UserIdentity(
        user_id=user.id,
        provider=str(provider),
        subject_id=subject_id,
        email=email,
        sso_groups=["existing-group"],
    )
    db.add(identity)
    await db.flush()
    return user, identity


async def _table_count(db: AsyncSession, model: type[User] | type[UserIdentity]) -> int:
    count = await db.scalar(select(func.count()).select_from(model))
    assert count is not None
    return count


async def _oidc_login(
    service: SsoService,
    provider: SsoProvider,
    redis_client,
    *,
    subject_id: str,
    email: str,
    groups: list[str],
) -> tuple[dict, str]:
    state = f"state-{uuid4().hex}"
    nonce = f"nonce-{uuid4().hex}"
    await redis_client.set(
        f"sso:oidc:state:{state}",
        json.dumps({"nonce": nonce, "provider_id": str(provider.id)}),
    )
    claims = {
        "iss": provider.issuer_url,
        "aud": provider.client_id,
        "sub": subject_id,
        "email": email,
        "groups": groups,
        "nonce": nonce,
    }
    with patch.object(service, "_exchange_code_for_token", return_value=(claims, "opaque-access-token")):
        return await service.process_oidc_callback(provider, state, "opaque-authorization-code")


@pytest.mark.asyncio
async def test_new_oidc_identity_cannot_claim_saml_username(db_session, redis_client):
    existing_role, _incoming_role, mapped_group = await _roles_and_mapping(db_session)
    shared_email = "cross-provider-collision@example.test"
    existing_user, _identity = await _seed_identity(
        db_session,
        role=existing_role,
        provider=AuthProvider.SAML,
        subject_id="existing-saml-subject",
        email=shared_email,
    )
    user_count = await _table_count(db_session, User)
    identity_count = await _table_count(db_session, UserIdentity)

    service = SsoService(db_session, redis_client)
    with pytest.raises(SsoValidationError, match=r"^SSO validation failed$"):
        await _oidc_login(
            service,
            _oidc_provider(),
            redis_client,
            subject_id="different-oidc-subject",
            email=shared_email,
            groups=[mapped_group],
        )

    assert await _table_count(db_session, User) == user_count
    assert await _table_count(db_session, UserIdentity) == identity_count
    await db_session.refresh(existing_user)
    assert existing_user.role_id == existing_role.id
    assert await redis_client.keys("session:*") == []


@pytest.mark.asyncio
async def test_identity_collision_audit_is_sanitized_authentication_failure(db_session, redis_client):
    existing_role, _incoming_role, mapped_group = await _roles_and_mapping(db_session)
    shared_email = "audit-collision@example.test"
    await _seed_identity(
        db_session,
        role=existing_role,
        provider=AuthProvider.SAML,
        subject_id="sensitive-saml-subject",
        email=shared_email,
    )

    service = SsoService(db_session, redis_client)
    with pytest.raises(SsoValidationError):
        await _oidc_login(
            service,
            _oidc_provider(),
            redis_client,
            subject_id="sensitive-oidc-subject",
            email=shared_email,
            groups=[mapped_group],
        )

    failure_entry = await db_session.scalar(
        select(AuditLogEntry)
        .where(AuditLogEntry.action_type == str(AuditActionType.AUTH_LOGIN_FAILURE))
        .order_by(AuditLogEntry.id.desc())
        .limit(1)
    )
    assert failure_entry is not None
    assert failure_entry.outcome == "failure"
    assert failure_entry.context == {
        "error_code": "[REDACTED]",
        "reason": "identity_collision",
    }

    stored_failure = json.dumps(
        {
            "actor_identity": failure_entry.actor_identity,
            "resource_id": failure_entry.resource_id,
            "context": failure_entry.context,
        }
    ).lower()
    for forbidden in (
        shared_email,
        "sensitive-saml-subject",
        "sensitive-oidc-subject",
        "oidc",
        "saml",
        "constraint",
        "insert into",
        "localhost",
        "traceback",
    ):
        assert forbidden not in stored_failure
