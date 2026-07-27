"""Regression coverage for fail-closed SSO identity collisions."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType, AuthProvider
from app.db.models.role import Role
from app.db.models.sso_group_mapping import SsoGroupMapping
from app.db.models.sso_provider import SsoProvider
from app.db.models.user import User
from app.db.models.user_identity import UserIdentity
from app.services.sso_service import (
    SsoIdentityCollisionError,
    SsoService,
    SsoValidationError,
)


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


def _saml_provider() -> SsoProvider:
    return SsoProvider(
        id=uuid4(),
        protocol="saml",
        display_name="Collision test SAML",
        group_claim_name="groups",
        saml_entity_id="urn:querycraft:collision-test",
        saml_metadata_url="https://identity.example.test/metadata",
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


async def _install_username_race_trigger(db: AsyncSession, username: str) -> None:
    assert "'" not in username
    suffix = uuid4().hex
    function_name = f"test_sso_username_race_{suffix}"
    trigger_name = f"test_sso_username_race_trigger_{suffix}"
    await db.execute(
        text(
            f"""
            CREATE FUNCTION {function_name}() RETURNS trigger AS $$
            BEGIN
                IF NEW.username = '{username}' THEN
                    RAISE unique_violation
                        USING MESSAGE = 'race-sensitive unique constraint collision';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    await db.execute(
        text(
            f"""
            CREATE TRIGGER {trigger_name}
            BEFORE INSERT ON users
            FOR EACH ROW EXECUTE FUNCTION {function_name}()
            """
        )
    )


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


async def _saml_login(
    service: SsoService,
    provider: SsoProvider,
    redis_client,
    *,
    subject_id: str,
    email: str,
    groups: list[str],
) -> tuple[dict, str]:
    request_id = f"request-{uuid4().hex}"
    await redis_client.set(
        f"sso:saml:request:{request_id}",
        json.dumps({"provider_id": str(provider.id)}),
    )
    attributes = {
        "subject_id": subject_id,
        "email": email,
        "groups": groups,
        "issuer": "https://identity.example.test",
        "not_before": None,
        "not_on_or_after": None,
        "assertion_id": f"assertion-{uuid4().hex}",
    }
    with patch.object(service, "_parse_saml_assertion", return_value=attributes):
        return await service.process_saml_callback(provider, "opaque-saml-response", request_id)


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
async def test_new_saml_identity_cannot_claim_oidc_username(db_session, redis_client):
    existing_role, _incoming_role, mapped_group = await _roles_and_mapping(db_session)
    shared_email = "reverse-cross-provider-collision@example.test"
    existing_user, _identity = await _seed_identity(
        db_session,
        role=existing_role,
        provider=AuthProvider.OIDC,
        subject_id="existing-oidc-subject",
        email=shared_email,
    )
    user_count = await _table_count(db_session, User)
    identity_count = await _table_count(db_session, UserIdentity)

    service = SsoService(db_session, redis_client)
    with pytest.raises(SsoValidationError, match=r"^SSO validation failed$"):
        await _saml_login(
            service,
            _saml_provider(),
            redis_client,
            subject_id="different-saml-subject",
            email=shared_email,
            groups=[mapped_group],
        )

    assert await _table_count(db_session, User) == user_count
    assert await _table_count(db_session, UserIdentity) == identity_count
    await db_session.refresh(existing_user)
    assert existing_user.role_id == existing_role.id
    assert await redis_client.keys("session:*") == []


@pytest.mark.asyncio
async def test_sso_identity_cannot_claim_builtin_admin_username(db_session, redis_client):
    _existing_role, _incoming_role, mapped_group = await _roles_and_mapping(db_session)
    admin = await db_session.scalar(select(User).where(User.is_builtin.is_(True)))
    assert admin is not None
    original_role_id = admin.role_id
    original_password_hash = admin.password_hash
    user_count = await _table_count(db_session, User)
    identity_count = await _table_count(db_session, UserIdentity)

    service = SsoService(db_session, redis_client)
    with pytest.raises(SsoValidationError, match=r"^SSO validation failed$"):
        await _oidc_login(
            service,
            _oidc_provider(),
            redis_client,
            subject_id="admin-collision-subject",
            email=admin.username,
            groups=[mapped_group],
        )

    assert await _table_count(db_session, User) == user_count
    assert await _table_count(db_session, UserIdentity) == identity_count
    await db_session.refresh(admin)
    assert admin.role_id == original_role_id
    assert admin.password_hash == original_password_hash
    assert admin.password_hash is not None
    assert admin.auth_provider == str(AuthProvider.LOCAL)
    assert admin.is_builtin is True
    assert await redis_client.keys("session:*") == []


@pytest.mark.asyncio
async def test_existing_provider_subject_reauthentication_updates_identity(db_session, redis_client):
    existing_role, incoming_role, mapped_group = await _roles_and_mapping(db_session)
    existing_user, identity = await _seed_identity(
        db_session,
        role=existing_role,
        provider=AuthProvider.OIDC,
        subject_id="returning-oidc-subject",
        email="returning-user@example.test",
    )

    service = SsoService(db_session, redis_client)
    profile, session_id = await _oidc_login(
        service,
        _oidc_provider(),
        redis_client,
        subject_id="returning-oidc-subject",
        email="updated-returning-user@example.test",
        groups=[mapped_group],
    )

    assert profile["user_id"] == str(existing_user.id)
    assert profile["role_id"] == str(incoming_role.id)
    await db_session.refresh(identity)
    await db_session.refresh(existing_user)
    assert identity.email == "updated-returning-user@example.test"
    assert identity.sso_groups == [mapped_group]
    assert identity.last_login_at is not None
    assert existing_user.role_id == incoming_role.id
    assert await redis_client.exists(f"session:{session_id}") == 1


@pytest.mark.asyncio
async def test_distinct_oidc_and_saml_usernames_both_sign_in(db_session, redis_client):
    _existing_role, _incoming_role, mapped_group = await _roles_and_mapping(db_session)
    user_count = await _table_count(db_session, User)
    identity_count = await _table_count(db_session, UserIdentity)
    service = SsoService(db_session, redis_client)

    oidc_profile, oidc_session_id = await _oidc_login(
        service,
        _oidc_provider(),
        redis_client,
        subject_id="distinct-oidc-subject",
        email="distinct-oidc-user@example.test",
        groups=[mapped_group],
    )
    saml_profile, saml_session_id = await _saml_login(
        service,
        _saml_provider(),
        redis_client,
        subject_id="distinct-saml-subject",
        email="distinct-saml-user@example.test",
        groups=[mapped_group],
    )

    assert oidc_profile["user_id"] != saml_profile["user_id"]
    assert await _table_count(db_session, User) == user_count + 2
    assert await _table_count(db_session, UserIdentity) == identity_count + 2
    assert await redis_client.exists(f"session:{oidc_session_id}") == 1
    assert await redis_client.exists(f"session:{saml_session_id}") == 1


@pytest.mark.asyncio
async def test_collision_callback_redirect_is_generic_and_sets_no_session_cookie():
    from app.api.v1.sso_auth import oidc_callback

    provider = _oidc_provider()
    service = AsyncMock()
    service.process_oidc_callback = AsyncMock(side_effect=SsoIdentityCollisionError())
    raw_code = "sensitive-authorization-code"
    raw_state = "sensitive-state"

    with (
        patch("app.api.v1.sso_auth._get_oidc_provider", new_callable=AsyncMock, return_value=provider),
        patch("app.api.v1.sso_auth.SsoService", return_value=service),
    ):
        response = await oidc_callback(
            code=raw_code,
            state=raw_state,
            db=AsyncMock(),
            redis=AsyncMock(),
        )

    assert response.status_code == 302
    assert response.headers["location"] == "/sign-in?error=sso_validation_failed"
    assert "set-cookie" not in response.headers
    redirect = response.headers["location"].lower()
    for forbidden in (
        raw_code,
        raw_state,
        "email",
        "username",
        "oidc",
        "subject",
        "constraint",
        "insert into",
        "localhost",
        "traceback",
    ):
        assert forbidden not in redirect


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


@pytest.mark.asyncio
async def test_database_uniqueness_race_rolls_back_identity_and_preserves_audit(db_session, redis_client):
    _existing_role, _incoming_role, mapped_group = await _roles_and_mapping(db_session)
    colliding_email = "database-race-collision@example.test"
    await _install_username_race_trigger(db_session, colliding_email)
    user_count = await _table_count(db_session, User)
    identity_count = await _table_count(db_session, UserIdentity)

    service = SsoService(db_session, redis_client)
    with pytest.raises(SsoValidationError, match=r"^SSO validation failed$") as collision:
        await _oidc_login(
            service,
            _oidc_provider(),
            redis_client,
            subject_id="database-race-subject",
            email=colliding_email,
            groups=[mapped_group],
        )

    failure_text = str(collision.value).lower()
    for forbidden in (
        colliding_email,
        "database-race-subject",
        "race-sensitive",
        "constraint",
        "insert into",
        "localhost",
        "traceback",
    ):
        assert forbidden not in failure_text

    assert await _table_count(db_session, User) == user_count
    assert await _table_count(db_session, UserIdentity) == identity_count
    failure_entry = await db_session.scalar(
        select(AuditLogEntry)
        .where(AuditLogEntry.action_type == str(AuditActionType.AUTH_LOGIN_FAILURE))
        .order_by(AuditLogEntry.id.desc())
        .limit(1)
    )
    assert failure_entry is not None
    assert failure_entry.context["reason"] == "identity_collision"
    assert await redis_client.keys("session:*") == []
