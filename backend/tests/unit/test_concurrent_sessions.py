"""Auth and SSO session-limit behavior with real Redis."""

import asyncio
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.enums import AuthProvider, SsoProtocol
from app.db.models.role import Role
from app.db.models.sso_provider import SsoProvider
from app.db.models.user import User
from app.db.models.user_identity import UserIdentity
from app.services.auth_service import AuthService
from app.services.sso_service import SsoService

LOCAL_USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440100")
SSO_OIDC_USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440200")
SSO_SAML_USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440201")
ROLE_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440300")


def _settings(max_sessions: int = 5) -> SimpleNamespace:
    return SimpleNamespace(
        SESSION_IDLE_TIMEOUT_HOURS=8,
        MAX_CONCURRENT_SESSIONS_PER_USER=max_sessions,
        PLATFORM_ENCRYPTION_KEY="d1OQc28ErbKH8nnhjNbchX5y_1EyXcfclkK1hPjPqFY=",
        BASE_URL="https://app.example.test",
    )


def _role() -> Role:
    role = Role(
        id=ROLE_ID,
        name="Analyst",
        permissions=["query.submit"],
    )
    return role


def _local_admin(user_id: uuid.UUID = LOCAL_USER_ID) -> User:
    user = User(
        id=user_id,
        username="admin",
        display_name="Admin",
        role="admin",
        password_hash="verified-by-test-boundary",
        auth_provider="local",
        role_id=None,
    )
    user.role_obj = Role(name="Admin", permissions=["query.submit"])
    return user


def _sso_provider(protocol: SsoProtocol = SsoProtocol.OIDC) -> SsoProvider:
    provider = SsoProvider()
    provider.id = uuid.UUID("550e8400-e29b-41d4-a716-446655440400")
    provider.protocol = protocol
    provider.display_name = "Test Provider"
    return provider


async def _members(redis_client, user_id: str) -> list[str]:
    return list(await redis_client.zrange(f"user_sessions:{user_id}", 0, -1))


async def _key_counts(redis_client, user_id: str, session_ids: list[str]) -> tuple[int, int, int]:
    live_key_counts = await asyncio.gather(
        *(redis_client.exists(f"session:{session_id}") for session_id in session_ids)
    )
    index_count = await redis_client.zcard(f"user_sessions:{user_id}")
    sequence_count = await redis_client.exists(f"user_sessions_seq:{user_id}")
    return sum(live_key_counts), index_count, sequence_count


async def _local_sign_in(redis_client, max_sessions: int, token_byte: int, timestamp: float):
    repo = SimpleNamespace(get_by_username=AsyncMock(return_value=_local_admin()))
    service = AuthService(repo, redis_client, settings=_settings(max_sessions=max_sessions))
    with (
        patch("app.services.auth_service.verify_password", return_value=True),
        patch("app.services.auth_service.os.urandom", return_value=bytes([token_byte]) * 32),
        patch("app.services.auth_service.time.time", side_effect=[timestamp, timestamp]),
    ):
        return await service.sign_in("admin", "secret")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_local_login_default_limit_keeps_five_newest_sessions(redis_client):
    user_id = str(LOCAL_USER_ID)

    created = []
    for index in range(6):
        _, session_id = await _local_sign_in(
            redis_client,
            max_sessions=5,
            token_byte=index + 1,
            timestamp=1000.0 + index,
        )
        created.append(session_id)

    assert await _members(redis_client, user_id) == created[1:]
    assert await redis_client.exists(f"session:{created[0]}") == 0
    assert await _key_counts(redis_client, user_id, created) == (5, 5, 1)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_local_login_creates_observable_session_payload_and_index(redis_client):
    user_id = str(LOCAL_USER_ID)

    profile, session_id = await _local_sign_in(redis_client, max_sessions=5, token_byte=9, timestamp=1500.0)
    session_payload = json.loads(await redis_client.get(f"session:{session_id}"))

    assert await _members(redis_client, user_id) == [session_id]
    assert profile.auth_provider == "local"
    assert profile.permissions == ["query.submit"]
    assert session_payload["user_id"] == user_id
    assert session_payload["username"] == "admin"
    assert session_payload["display_name"] == "Admin"
    assert session_payload["role"] == "admin"
    assert session_payload["role_name"] == "Admin"
    assert session_payload["permissions"] == ["query.submit"]
    assert session_payload["auth_provider"] == "local"
    assert session_payload["subject_id"] == "admin"
    assert "created_at" in session_payload
    assert "last_activity" in session_payload


@pytest.mark.integration
@pytest.mark.asyncio
async def test_local_login_custom_lowered_limit_evicts_to_new_limit(redis_client):
    user_id = str(LOCAL_USER_ID)

    first = []
    for index in range(4):
        _, session_id = await _local_sign_in(
            redis_client,
            max_sessions=4,
            token_byte=index + 10,
            timestamp=2000.0 + index,
        )
        first.append(session_id)

    _, lowered_session_id = await _local_sign_in(redis_client, max_sessions=2, token_byte=99, timestamp=3000.0)

    assert await _members(redis_client, user_id) == [first[-1], lowered_session_id]
    assert await _key_counts(redis_client, user_id, [*first, lowered_session_id]) == (2, 2, 1)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("max_sessions", [0, -1])
async def test_local_login_unlimited_mode_still_indexes_every_session(redis_client, max_sessions):
    user_id = str(LOCAL_USER_ID)

    created = []
    for index in range(7):
        _, session_id = await _local_sign_in(
            redis_client, max_sessions=max_sessions, token_byte=index + 30, timestamp=4000.0 + index
        )
        created.append(session_id)

    assert await _members(redis_client, user_id) == created
    assert await _key_counts(redis_client, user_id, created) == (7, 7, 1)


async def _sso_sign_in(redis_client, auth_provider: AuthProvider, max_sessions: int, subject_suffix: str):
    db = AsyncMock()
    db.add = MagicMock()
    with patch("app.services.sso_service.get_settings", return_value=_settings(max_sessions=max_sessions)):
        service = SsoService(db, redis_client)
    role = _role()
    user_id = SSO_OIDC_USER_ID if subject_suffix == "oidc" else SSO_SAML_USER_ID
    username = f"sso-{subject_suffix}@example.test"
    identity_result = MagicMock()
    identity_result.scalar_one_or_none.return_value = None
    username_result = MagicMock()
    username_result.scalar_one_or_none.return_value = None
    db.execute.side_effect = [identity_result, username_result]
    db.begin_nested.return_value = AsyncMock(commit=AsyncMock(), rollback=AsyncMock())

    async def refresh_user(created_user):
        created_user.id = user_id
        created_user.username = username
        created_user.display_name = username
        created_user.role = "viewer"

    db.refresh.side_effect = refresh_user

    with patch.object(service, "resolve_role_from_groups", new=AsyncMock(return_value=role)):
        return await service._resolve_role_and_create_session(
            provider=_sso_provider(SsoProtocol.SAML if auth_provider == AuthProvider.SAML else SsoProtocol.OIDC),
            subject_id=f"subject-{subject_suffix}",
            email=username,
            groups=["analysts"],
            auth_provider=auth_provider,
        )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("auth_provider", [AuthProvider.OIDC, AuthProvider.SAML])
async def test_sso_session_creation_creates_matching_key_and_index_member(redis_client, auth_provider):
    profile, session_id = await _sso_sign_in(
        redis_client,
        auth_provider,
        max_sessions=5,
        subject_suffix=auth_provider.value,
    )
    user_id = profile["user_id"]
    session_payload = json.loads(await redis_client.get(f"session:{session_id}"))

    assert await _members(redis_client, user_id) == [session_id]
    assert session_payload["auth_provider"] == str(auth_provider)
    assert session_payload["role_name"] == "Analyst"


class _BarrierUserRepository:
    def __init__(self, user: User, burst_size: int):
        self._user = user
        self._burst_size = burst_size
        self._seen = 0
        self._ready = asyncio.Event()

    async def get_by_username(self, _username: str) -> User:
        self._seen += 1
        if self._seen == self._burst_size:
            self._ready.set()
        await self._ready.wait()
        return self._user

    async def get_by_id(self, _user_id: uuid.UUID) -> User:
        return self._user


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simultaneous_local_login_burst_keeps_newest_linearized_sessions(redis_client):
    user_id = str(LOCAL_USER_ID)
    burst_size = 8
    repo = _BarrierUserRepository(_local_admin(), burst_size=burst_size)
    service = AuthService(repo, redis_client, settings=_settings(max_sessions=3))
    tokens = [bytes([index + 1]) * 32 for index in range(burst_size)]

    async def sign_in_once():
        return await service.sign_in("admin", "secret")

    with (
        patch("app.services.auth_service.verify_password", return_value=True),
        patch("app.services.auth_service.os.urandom", side_effect=tokens),
        patch("app.services.auth_service.time.time", return_value=6000.0),
    ):
        results = await asyncio.gather(*(sign_in_once() for _ in range(burst_size)))

    created = [session_id for _profile, session_id in results]
    live_members = await _members(redis_client, user_id)
    live_scores = await redis_client.zrange(f"user_sessions:{user_id}", 0, -1, withscores=True)
    assert len(live_members) == 3
    assert live_members == [member for member, _score in live_scores]
    assert live_scores == sorted(live_scores, key=lambda item: item[1])
    assert await _key_counts(redis_client, user_id, created) == (3, 3, 1)
    for evicted in set(created) - set(live_members):
        with pytest.raises(Exception) as exc_info:
            await service.get_me(evicted)
        assert getattr(exc_info.value, "status_code", None) == 401


class _ExistingIdentityDb:
    def __init__(self, user: User, provider: AuthProvider = AuthProvider.OIDC):
        self._identity = UserIdentity(
            id=uuid.UUID("550e8400-e29b-41d4-a716-446655440500"),
            user_id=user.id,
            provider=str(provider),
            subject_id="sso-subject",
            email=user.username,
            sso_groups=["analysts"],
        )
        self._user = user

    async def execute(self, statement):
        result = MagicMock()
        statement_text = str(statement)
        if "user_identities" in statement_text:
            result.scalar_one_or_none.return_value = self._identity
        else:
            result.scalar_one.return_value = self._user
        return result

    async def flush(self):
        return None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simultaneous_sso_session_burst_keeps_newest_linearized_sessions(redis_client):
    user = User(
        id=SSO_OIDC_USER_ID,
        username="sso-burst@example.test",
        display_name="SSO Burst",
        password_hash=None,
        role="viewer",
        role_id=ROLE_ID,
        auth_provider="oidc",
    )
    db = _ExistingIdentityDb(user)
    with patch("app.services.sso_service.get_settings", return_value=_settings(max_sessions=2)):
        service = SsoService(db, redis_client)
    role = _role()
    tokens = [bytes([index + 40]) * 32 for index in range(6)]

    async def sso_once():
        return await service._resolve_role_and_create_session(
            provider=_sso_provider(SsoProtocol.OIDC),
            subject_id="sso-subject",
            email=user.username,
            groups=["analysts"],
            auth_provider=AuthProvider.OIDC,
        )

    with (
        patch.object(service, "resolve_role_from_groups", new=AsyncMock(return_value=role)),
        patch("app.services.sso_service.os.urandom", side_effect=tokens),
        patch("app.services.sso_service.time.time", return_value=7000.0),
    ):
        results = await asyncio.gather(*(sso_once() for _ in range(6)))

    created = [session_id for _profile, session_id in results]
    user_id = str(user.id)
    assert len(await _members(redis_client, user_id)) == 2
    assert await _key_counts(redis_client, user_id, created) == (2, 2, 1)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("auth_provider", [AuthProvider.OIDC, AuthProvider.SAML])
async def test_sso_callback_failed_audit_rolls_back_session_index_and_sequence(redis_client, auth_provider):
    user_id = SSO_OIDC_USER_ID if auth_provider == AuthProvider.OIDC else SSO_SAML_USER_ID
    user = User(
        id=user_id,
        username=f"{auth_provider.value}-audit@example.test",
        display_name="SSO Audit",
        password_hash=None,
        role="viewer",
        role_id=ROLE_ID,
        auth_provider=str(auth_provider),
    )
    db = _ExistingIdentityDb(user, provider=auth_provider)
    protocol = SsoProtocol.OIDC if auth_provider == AuthProvider.OIDC else SsoProtocol.SAML
    provider = _sso_provider(protocol)
    with patch("app.services.sso_service.get_settings", return_value=_settings(max_sessions=5)):
        service = SsoService(db, redis_client)
    role = _role()
    token = bytes([55 if auth_provider == AuthProvider.OIDC else 56]) * 32

    with (
        patch.object(service, "resolve_role_from_groups", new=AsyncMock(return_value=role)),
        patch("app.services.sso_service.os.urandom", return_value=token),
        patch("app.services.sso_service.time.time", side_effect=[8000.0, 8000.0]),
        patch("app.services.sso_service.AuditService.log", side_effect=[None, RuntimeError("audit unavailable")]),
        pytest.raises(RuntimeError, match="audit unavailable"),
    ):
        if auth_provider == AuthProvider.OIDC:
            await redis_client.set(
                "sso:oidc:state:audit-state",
                json.dumps({"nonce": "nonce-1", "provider_id": str(provider.id)}),
                ex=3600,
            )
            with (
                patch.object(
                    service,
                    "_exchange_code_for_token",
                    new=AsyncMock(
                        return_value=(
                            {"sub": "sso-subject", "email": user.username, "groups": ["analysts"]},
                            "[redacted-by-test]",
                        )
                    ),
                ),
                patch.object(service, "_validate_oidc_claims", return_value=None),
            ):
                await service.process_oidc_callback(provider, "audit-state", "code")
        else:
            await redis_client.set(
                "sso:saml:request:audit-request",
                json.dumps({"provider_id": str(provider.id)}),
                ex=3600,
            )
            with (
                patch.object(
                    service,
                    "_parse_saml_assertion",
                    return_value={"subject_id": "sso-subject", "email": user.username, "groups": ["analysts"]},
                ),
                patch.object(service, "_validate_saml_assertion", return_value=None),
            ):
                await service.process_saml_callback(provider, "saml-response", "audit-request")

    session_id = token.hex()
    assert await redis_client.exists(f"session:{session_id}") == 0
    assert await redis_client.exists(f"user_sessions:{user_id}") == 0
    assert await redis_client.exists(f"user_sessions_seq:{user_id}") == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sign_out_removes_session_index_and_sequence(redis_client):
    user_id = str(LOCAL_USER_ID)
    _, session_id = await _local_sign_in(redis_client, max_sessions=1, token_byte=88, timestamp=5000.0)
    service = AuthService(
        SimpleNamespace(get_by_username=AsyncMock()),
        redis_client,
        settings=_settings(max_sessions=1),
    )

    await service.sign_out(session_id)

    assert await redis_client.exists(f"session:{session_id}") == 0
    assert await redis_client.exists(f"user_sessions:{user_id}") == 0
    assert await redis_client.exists(f"user_sessions_seq:{user_id}") == 0
