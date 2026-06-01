"""TDD tests for concurrent session limit (T-656).

Tests for:
- Max concurrent sessions per user defaults to 5 (configurable)
- Oldest session evicted on overflow
- Applies to local admin login (AuthService.sign_in)
- Applies to SSO login session creation (SsoService._resolve_role_and_create_session)
- Built-in admin local login guarantee preserved (limit evicts, never blocks login)
- Session eviction does not leak raw session IDs, user UUIDs, usernames, or auth-provider details
- Redis user session index (sorted set) maintained on create and delete
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.enums import AuthProvider, SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.services.auth_service import AuthService
from app.services.sso_service import SsoService, SsoValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session_data(
    user_id="550e8400-e29b-41d4-a716-446655440000",
    username="admin",
    created_at=1000.0,
    last_activity=1000.0,
    auth_provider="local",
    role_id=None,
    role_name=None,
    permissions=None,
):
    return {
        "user_id": user_id,
        "username": username,
        "display_name": username,
        "role": "admin" if username == "admin" else "viewer",
        "role_id": role_id,
        "role_name": role_name,
        "permissions": permissions or [],
        "auth_provider": auth_provider,
        "subject_id": username,
        "created_at": created_at,
        "last_activity": last_activity,
    }


def _make_user(
    username="admin",
    auth_provider="local",
    role="admin",
    is_builtin=True,
    role_id=None,
    role_obj=None,
):
    from app.core.security import hash_password

    user = MagicMock()
    user.id = "550e8400-e29b-41d4-a716-446655440000"
    user.username = username
    user.display_name = username.title()
    user.role = role
    user.password_hash = hash_password("secret") if auth_provider == "local" else None
    user.auth_provider = auth_provider
    user.is_builtin = is_builtin
    user.role_id = role_id
    user.role_obj = role_obj
    return user


# ---------------------------------------------------------------------------
# AuthService concurrent session limit tests
# ---------------------------------------------------------------------------

class TestAuthServiceConcurrentSessions:
    """AuthService.sign_in must enforce max concurrent sessions per user."""

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.get_by_username = AsyncMock()
        repo.get_by_id = AsyncMock()
        return repo

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=1)
        redis.get = AsyncMock(return_value=None)
        redis.zadd = AsyncMock(return_value=1)
        redis.zcard = AsyncMock(return_value=0)
        redis.zrange = AsyncMock(return_value=[])
        redis.zrem = AsyncMock(return_value=1)
        redis.zremrangebyrank = AsyncMock(return_value=0)
        return redis

    @pytest.fixture
    def service(self, mock_repo, mock_redis):
        svc = AuthService(mock_repo, mock_redis)
        svc._settings.SESSION_IDLE_TIMEOUT_HOURS = 8
        svc._settings.MAX_CONCURRENT_SESSIONS_PER_USER = 5
        return svc

    @pytest.mark.asyncio
    async def test_sign_in_adds_session_to_user_index(self, service, mock_repo, mock_redis):
        """New session is added to Redis sorted set keyed by user."""
        admin_user = _make_user()
        admin_user.role_obj = MagicMock()
        admin_user.role_obj.name = "Admin"
        admin_user.role_obj.permissions = ["query.submit"]
        mock_repo.get_by_username.return_value = admin_user

        profile, session_id = await service.sign_in("admin", "secret")
        assert profile.username == "admin"
        # zadd called with user session index
        zadd_calls = [c for c in mock_redis.zadd.call_args_list if "user_sessions" in str(c[0][0])]
        assert len(zadd_calls) == 1
        user_index_key = zadd_calls[0][0][0]
        assert user_index_key.startswith("user_sessions:")
        assert "550e8400" in user_index_key  # user_id substring

    @pytest.mark.asyncio
    async def test_sign_in_under_limit_no_eviction(self, service, mock_repo, mock_redis):
        """User with 4 existing sessions (under limit 5) gets a 5th with no eviction."""
        admin_user = _make_user()
        admin_user.role_obj = MagicMock()
        admin_user.role_obj.name = "Admin"
        admin_user.role_obj.permissions = ["query.submit"]
        mock_repo.get_by_username.return_value = admin_user

        mock_redis.zcard.return_value = 4

        profile, session_id = await service.sign_in("admin", "secret")
        assert profile is not None
        mock_redis.zremrangebyrank.assert_not_called()
        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_sign_in_at_limit_evicts_oldest(self, service, mock_repo, mock_redis):
        """User with 5 existing sessions (at limit) gets oldest evicted before new created."""
        admin_user = _make_user()
        admin_user.role_obj = MagicMock()
        admin_user.role_obj.name = "Admin"
        admin_user.role_obj.permissions = ["query.submit"]
        mock_repo.get_by_username.return_value = admin_user

        mock_redis.zcard.return_value = 6  # 5 existing + 1 new after zadd
        mock_redis.zrange.return_value = ["oldest-session-id"]

        profile, session_id = await service.sign_in("admin", "secret")
        assert profile is not None
        # Should evict overflow = 6 - 5 = 1 oldest
        # Implementation uses zrange(0, 0) -> zrem -> delete
        mock_redis.zrange.assert_awaited()
        zrange_calls = [c for c in mock_redis.zrange.call_args_list if "user_sessions:" in str(c[0][0])]
        assert len(zrange_calls) >= 1
        # Session key also deleted
        delete_calls = [c for c in mock_redis.delete.call_args_list if "session:" in str(c[0][0])]
        assert any("oldest-session-id" in str(c[0]) for c in delete_calls)
        # Removed from user index
        zrem_calls = [c for c in mock_redis.zrem.call_args_list if "oldest-session-id" in str(c[0])]
        assert len(zrem_calls) >= 1

    @pytest.mark.asyncio
    async def test_sign_in_over_limit_evicts_multiple_oldest(self, service, mock_repo, mock_redis):
        """If somehow user has 7 sessions, evict 3 oldest to get back to 5."""
        admin_user = _make_user()
        admin_user.role_obj = MagicMock()
        admin_user.role_obj.name = "Admin"
        admin_user.role_obj.permissions = ["query.submit"]
        mock_repo.get_by_username.return_value = admin_user

        mock_redis.zcard.return_value = 8  # 7 existing + 1 new after zadd
        mock_redis.zrange.return_value = ["s1", "s2", "s3"]

        profile, session_id = await service.sign_in("admin", "secret")
        assert profile is not None
        # Evict 8 - 5 = 3 oldest
        zrange_calls = [c for c in mock_redis.zrange.call_args_list if "user_sessions:" in str(c[0][0])]
        assert len(zrange_calls) >= 1
        zrange_args = zrange_calls[-1][0]
        assert zrange_args[1] == 0
        assert zrange_args[2] == 2  # rank 0 through 2 = 3 items

    @pytest.mark.asyncio
    async def test_builtin_admin_always_allowed_despite_limit(self, service, mock_repo, mock_redis):
        """Built-in admin login succeeds even at session limit; oldest is evicted."""
        admin_user = _make_user(is_builtin=True)
        admin_user.role_obj = MagicMock()
        admin_user.role_obj.name = "Admin"
        admin_user.role_obj.permissions = ["query.submit", "admin.sso.manage"]
        mock_repo.get_by_username.return_value = admin_user

        mock_redis.zcard.return_value = 6  # 5 existing + 1 new after zadd
        mock_redis.zrange.return_value = ["old-session"]

        profile, session_id = await service.sign_in("admin", "secret")
        assert profile.username == "admin"
        assert session_id is not None
        # Eviction happened, not a hard block
        zrange_calls = [c for c in mock_redis.zrange.call_args_list if "user_sessions:" in str(c[0][0])]
        assert len(zrange_calls) >= 1

    @pytest.mark.asyncio
    async def test_eviction_does_not_leak_session_id_in_response(self, service, mock_repo, mock_redis):
        """When eviction occurs, the returned profile/session_id contain no raw evicted IDs."""
        admin_user = _make_user()
        admin_user.role_obj = MagicMock()
        admin_user.role_obj.name = "Admin"
        admin_user.role_obj.permissions = ["query.submit"]
        mock_repo.get_by_username.return_value = admin_user

        mock_redis.zcard.return_value = 5
        mock_redis.zrange.return_value = ["secret-session-id-12345"]

        profile, session_id = await service.sign_in("admin", "secret")
        # profile should not contain the evicted session ID
        profile_json = json.dumps(profile.model_dump() if hasattr(profile, "model_dump") else dict(profile))
        assert "secret-session-id-12345" not in profile_json
        # New session_id is different
        assert session_id != "secret-session-id-12345"

    @pytest.mark.asyncio
    async def test_eviction_does_not_leak_username_or_uuid(self, service, mock_repo, mock_redis):
        """Eviction operation uses internal Redis keys but does not expose them in errors."""
        admin_user = _make_user()
        admin_user.role_obj = MagicMock()
        admin_user.role_obj.name = "Admin"
        admin_user.role_obj.permissions = ["query.submit"]
        mock_repo.get_by_username.return_value = admin_user

        mock_redis.zcard.return_value = 6  # 5 existing + 1 new after zadd
        mock_redis.zrange.return_value = ["old-session"]
        # Even if Redis delete fails, error should be sanitized
        mock_redis.delete.side_effect = RuntimeError("Redis connection lost")

        with pytest.raises(Exception) as exc_info:
            await service.sign_in("admin", "secret")

        error_str = str(exc_info.value)
        assert "old-session" not in error_str
        assert "550e8400" not in error_str  # user UUID
        assert "admin" not in error_str.lower() or "internal" in error_str.lower()

    @pytest.mark.asyncio
    async def test_custom_max_sessions_setting_respected(self, mock_repo, mock_redis):
        """MAX_CONCURRENT_SESSIONS_PER_USER=3 is respected."""
        svc = AuthService(mock_repo, mock_redis)
        svc._settings.SESSION_IDLE_TIMEOUT_HOURS = 8
        svc._settings.MAX_CONCURRENT_SESSIONS_PER_USER = 3

        admin_user = _make_user()
        admin_user.role_obj = MagicMock()
        admin_user.role_obj.name = "Admin"
        admin_user.role_obj.permissions = ["query.submit"]
        mock_repo.get_by_username.return_value = admin_user

        mock_redis.zcard.return_value = 4  # 3 existing + 1 new after zadd
        mock_redis.zrange.return_value = ["oldest"]

        profile, session_id = await svc.sign_in("admin", "secret")
        assert profile is not None
        zrange_calls = [c for c in mock_redis.zrange.call_args_list if "user_sessions:" in str(c[0][0])]
        assert len(zrange_calls) >= 1
        zrange_args = zrange_calls[-1][0]
        assert zrange_args[1] == 0
        assert zrange_args[2] == 0  # evict 1 (4 - 3 = 1)

    @pytest.mark.asyncio
    async def test_sign_out_removes_from_user_index(self, service, mock_repo, mock_redis):
        """sign_out deletes session key and removes from user session index."""
        mock_redis.get.return_value = json.dumps(
            {"user_id": "550e8400-e29b-41d4-a716-446655440000", "username": "admin"}
        )
        await service.sign_out("session-abc")
        # Delete the session key
        mock_redis.delete.assert_any_await("session:session-abc")
        # Also remove from user index (zrem is called with session id)
        zrem_calls = [c for c in mock_redis.zrem.call_args_list if "session-abc" in str(c[0])]
        assert len(zrem_calls) >= 1


# ---------------------------------------------------------------------------
# SsoService concurrent session limit tests
# ---------------------------------------------------------------------------

class TestSsoServiceConcurrentSessions:
    """SsoService._resolve_role_and_create_session must enforce max concurrent sessions."""

    @pytest.fixture
    def oidc_provider(self):
        provider = MagicMock(spec=SsoProvider)
        provider.id = "oidc-provider-uuid"
        provider.protocol = SsoProtocol.OIDC
        provider.display_name = "Test OIDC"
        provider.issuer_url = "https://idp.example.com"
        provider.client_id = "test-client-id"
        provider.encrypted_client_secret = "enc-secret"
        provider.scopes = "openid email profile groups"
        provider.redirect_uri = "https://app.example.com/api/v1/auth/sso/oidc/callback"
        provider.group_claim_name = "groups"
        return provider

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=1)
        redis.get = AsyncMock(return_value=None)
        redis.zadd = AsyncMock(return_value=1)
        redis.zcard = AsyncMock(return_value=0)
        redis.zrange = AsyncMock(return_value=[])
        redis.zrem = AsyncMock(return_value=1)
        redis.zremrangebyrank = AsyncMock(return_value=0)
        return redis

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def sso_service(self, mock_db, mock_redis):
        with patch("app.services.sso_service.get_settings") as mock_settings:
            settings = MagicMock()
            settings.PLATFORM_ENCRYPTION_KEY = "d1OQc28ErbKH8nnhjNbchX5y_1EyXcfclkK1hPjPqFY="
            settings.SESSION_IDLE_TIMEOUT_HOURS = 8
            settings.MAX_CONCURRENT_SESSIONS_PER_USER = 5
            settings.BASE_URL = "https://app.example.com"
            mock_settings.return_value = settings
            return SsoService(mock_db, mock_redis)

    @pytest.mark.asyncio
    async def test_sso_login_adds_session_to_user_index(self, sso_service, oidc_provider, mock_db, mock_redis):
        """SSO session creation adds session to user session sorted set."""
        # Setup role resolution
        role = MagicMock()
        role.id = "role-uuid-1"
        role.name = "Analyst"
        role.permissions = ["query.submit"]

        user = MagicMock()
        user.id = "550e8400-e29b-41d4-a716-446655440000"
        user.username = "sso_user@example.com"
        user.display_name = "SSO User"
        user.role = "viewer"
        user.role_id = role.id
        user.auth_provider = "oidc"

        # Mock DB queries for role resolution and user identity
        with patch.object(sso_service, "resolve_role_from_groups", new_callable=AsyncMock) as mock_resolve_role:
            mock_resolve_role.return_value = role
            with patch.object(sso_service._db, "execute") as mock_execute:
                # First execute: identity lookup (None -> create)
                # Second execute: user lookup after identity creation
                identity_result = MagicMock()
                identity_result.scalar_one_or_none.return_value = None

                user_result = MagicMock()
                user_result.scalar_one.return_value = user

                mock_execute.side_effect = [identity_result, user_result]

                profile, session_id = await sso_service._resolve_role_and_create_session(
                    provider=oidc_provider,
                    subject_id="sub-123",
                    email="sso_user@example.com",
                    groups=["analysts"],
                    auth_provider=AuthProvider.OIDC,
                )

        assert profile is not None
        assert session_id is not None
        zadd_calls = [c for c in mock_redis.zadd.call_args_list if "user_sessions" in str(c[0][0])]
        assert len(zadd_calls) == 1
        user_index_key = zadd_calls[0][0][0]
        assert user_index_key.startswith("user_sessions:")

    @pytest.mark.asyncio
    async def test_sso_login_at_limit_evicts_oldest(self, sso_service, oidc_provider, mock_db, mock_redis):
        """SSO login at session limit evicts oldest session before creating new."""
        role = MagicMock()
        role.id = "role-uuid-1"
        role.name = "Analyst"
        role.permissions = ["query.submit"]

        user = MagicMock()
        user.id = "550e8400-e29b-41d4-a716-446655440000"
        user.username = "sso_user@example.com"
        user.display_name = "SSO User"
        user.role = "viewer"
        user.role_id = role.id
        user.auth_provider = "oidc"

        mock_redis.zcard.return_value = 6  # 5 existing + 1 new after zadd
        mock_redis.zrange.return_value = ["oldest-sso-session"]

        with patch.object(sso_service, "resolve_role_from_groups", new_callable=AsyncMock) as mock_resolve_role:
            mock_resolve_role.return_value = role
            with patch.object(sso_service._db, "execute") as mock_execute:
                identity_result = MagicMock()
                identity_result.scalar_one_or_none.return_value = None
                user_result = MagicMock()
                user_result.scalar_one.return_value = user
                mock_execute.side_effect = [identity_result, user_result]

                profile, session_id = await sso_service._resolve_role_and_create_session(
                    provider=oidc_provider,
                    subject_id="sub-123",
                    email="sso_user@example.com",
                    groups=["analysts"],
                    auth_provider=AuthProvider.OIDC,
                )

        assert profile is not None
        zrange_calls = [c for c in mock_redis.zrange.call_args_list if "user_sessions:" in str(c[0][0])]
        assert len(zrange_calls) >= 1
        delete_calls = [c for c in mock_redis.delete.call_args_list if "oldest-sso-session" in str(c[0])]
        assert len(delete_calls) >= 1
        zrem_calls = [c for c in mock_redis.zrem.call_args_list if "oldest-sso-session" in str(c[0])]
        assert len(zrem_calls) >= 1

    @pytest.mark.asyncio
    async def test_sso_login_under_limit_no_eviction(self, sso_service, oidc_provider, mock_db, mock_redis):
        """SSO login under limit creates session without eviction."""
        role = MagicMock()
        role.id = "role-uuid-1"
        role.name = "Analyst"
        role.permissions = ["query.submit"]

        user = MagicMock()
        user.id = "550e8400-e29b-41d4-a716-446655440000"
        user.username = "sso_user@example.com"
        user.display_name = "SSO User"
        user.role = "viewer"
        user.role_id = role.id
        user.auth_provider = "oidc"

        mock_redis.zcard.return_value = 2

        with patch.object(sso_service, "resolve_role_from_groups", new_callable=AsyncMock) as mock_resolve_role:
            mock_resolve_role.return_value = role
            with patch.object(sso_service._db, "execute") as mock_execute:
                identity_result = MagicMock()
                identity_result.scalar_one_or_none.return_value = None
                user_result = MagicMock()
                user_result.scalar_one.return_value = user
                mock_execute.side_effect = [identity_result, user_result]

                profile, session_id = await sso_service._resolve_role_and_create_session(
                    provider=oidc_provider,
                    subject_id="sub-123",
                    email="sso_user@example.com",
                    groups=["analysts"],
                    auth_provider=AuthProvider.OIDC,
                )

        assert profile is not None
        # No zrange/zrem/delete for eviction should happen
        zrange_calls = [c for c in mock_redis.zrange.call_args_list if "user_sessions:" in str(c[0][0])]
        assert len(zrange_calls) == 0

    @pytest.mark.asyncio
    async def test_sso_eviction_does_not_leak_sensitive_data(self, sso_service, oidc_provider, mock_db, mock_redis):
        """SSO session eviction does not expose session IDs or user details in errors."""
        role = MagicMock()
        role.id = "role-uuid-1"
        role.name = "Analyst"
        role.permissions = ["query.submit"]

        user = MagicMock()
        user.id = "550e8400-e29b-41d4-a716-446655440000"
        user.username = "sso_user@example.com"
        user.display_name = "SSO User"
        user.role = "viewer"
        user.role_id = role.id
        user.auth_provider = "oidc"

        mock_redis.zcard.return_value = 6  # 5 existing + 1 new after zadd
        mock_redis.zrange.return_value = ["leaky-session-id"]
        mock_redis.delete.side_effect = RuntimeError("Redis failure")

        with patch.object(sso_service, "resolve_role_from_groups", new_callable=AsyncMock) as mock_resolve_role:
            mock_resolve_role.return_value = role
            with patch.object(sso_service._db, "execute") as mock_execute:
                identity_result = MagicMock()
                identity_result.scalar_one_or_none.return_value = None
                user_result = MagicMock()
                user_result.scalar_one.return_value = user
                mock_execute.side_effect = [identity_result, user_result]

                with pytest.raises(Exception) as exc_info:
                    await sso_service._resolve_role_and_create_session(
                        provider=oidc_provider,
                        subject_id="sub-123",
                        email="sso_user@example.com",
                        groups=["analysts"],
                        auth_provider=AuthProvider.OIDC,
                    )

        error_str = str(exc_info.value)
        assert "leaky-session-id" not in error_str
        assert "550e8400" not in error_str
        assert "sso_user" not in error_str.lower() or "internal" in error_str.lower()

    @pytest.mark.asyncio
    async def test_sso_custom_max_sessions_respected(self, mock_db, mock_redis, oidc_provider):
        """Custom MAX_CONCURRENT_SESSIONS_PER_USER=2 is respected for SSO."""
        with patch("app.services.sso_service.get_settings") as mock_settings:
            settings = MagicMock()
            settings.PLATFORM_ENCRYPTION_KEY = "d1OQc28ErbKH8nnhjNbchX5y_1EyXcfclkK1hPjPqFY="
            settings.SESSION_IDLE_TIMEOUT_HOURS = 8
            settings.MAX_CONCURRENT_SESSIONS_PER_USER = 2
            settings.BASE_URL = "https://app.example.com"
            mock_settings.return_value = settings
            sso_service = SsoService(mock_db, mock_redis)

        role = MagicMock()
        role.id = "role-uuid-1"
        role.name = "Analyst"
        role.permissions = ["query.submit"]

        user = MagicMock()
        user.id = "550e8400-e29b-41d4-a716-446655440000"
        user.username = "sso_user@example.com"
        user.display_name = "SSO User"
        user.role = "viewer"
        user.role_id = role.id
        user.auth_provider = "oidc"

        mock_redis.zcard.return_value = 3  # 2 existing + 1 new after zadd
        mock_redis.zrange.return_value = ["old1"]

        with patch.object(sso_service, "resolve_role_from_groups", new_callable=AsyncMock) as mock_resolve_role:
            mock_resolve_role.return_value = role
            with patch.object(sso_service._db, "execute") as mock_execute:
                identity_result = MagicMock()
                identity_result.scalar_one_or_none.return_value = None
                user_result = MagicMock()
                user_result.scalar_one.return_value = user
                mock_execute.side_effect = [identity_result, user_result]

                profile, session_id = await sso_service._resolve_role_and_create_session(
                    provider=oidc_provider,
                    subject_id="sub-123",
                    email="sso_user@example.com",
                    groups=["analysts"],
                    auth_provider=AuthProvider.OIDC,
                )

        assert profile is not None
        zrange_calls = [c for c in mock_redis.zrange.call_args_list if "user_sessions:" in str(c[0][0])]
        assert len(zrange_calls) >= 1
        zrange_args = zrange_calls[-1][0]
        assert zrange_args[1] == 0
        assert zrange_args[2] == 0  # evict 1 oldest


# ---------------------------------------------------------------------------
# SessionMiddleware / sign_out user index cleanup tests
# ---------------------------------------------------------------------------

class TestSessionIndexCleanup:
    """sign_out and session expiry must clean up user session index."""

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.get_by_username = AsyncMock()
        repo.get_by_id = AsyncMock()
        return repo

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=1)
        redis.get = AsyncMock(return_value=None)
        redis.zadd = AsyncMock(return_value=1)
        redis.zcard = AsyncMock(return_value=0)
        redis.zrange = AsyncMock(return_value=[])
        redis.zrem = AsyncMock(return_value=1)
        redis.zremrangebyrank = AsyncMock(return_value=0)
        return redis

    @pytest.fixture
    def service(self, mock_repo, mock_redis):
        svc = AuthService(mock_repo, mock_redis)
        svc._settings.SESSION_IDLE_TIMEOUT_HOURS = 8
        svc._settings.MAX_CONCURRENT_SESSIONS_PER_USER = 5
        return svc

    @pytest.mark.asyncio
    async def test_sign_out_deletes_session_and_index_entry(self, service, mock_redis):
        """sign_out removes session key and zrem from user index."""
        mock_redis.get.return_value = json.dumps(
            {"user_id": "550e8400-e29b-41d4-a716-446655440000", "username": "admin"}
        )
        await service.sign_out("session-to-delete")
        mock_redis.delete.assert_any_await("session:session-to-delete")
        # zrem should be called for the user index
        zrem_calls = [c for c in mock_redis.zrem.call_args_list if "session-to-delete" in str(c[0])]
        assert len(zrem_calls) >= 1


# ---------------------------------------------------------------------------
# Config / edge case tests
# ---------------------------------------------------------------------------

class TestConcurrentSessionConfig:
    """Configuration and edge cases for concurrent session limit."""

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.get_by_username = AsyncMock()
        repo.get_by_id = AsyncMock()
        return repo

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=1)
        redis.get = AsyncMock(return_value=None)
        redis.zadd = AsyncMock(return_value=1)
        redis.zcard = AsyncMock(return_value=0)
        redis.zrange = AsyncMock(return_value=[])
        redis.zrem = AsyncMock(return_value=1)
        redis.zremrangebyrank = AsyncMock(return_value=0)
        return redis

    @pytest.mark.asyncio
    async def test_zero_or_negative_max_sessions_treated_as_no_limit(self, mock_repo, mock_redis):
        """MAX_CONCURRENT_SESSIONS_PER_USER <= 0 disables limit (no eviction)."""
        svc = AuthService(mock_repo, mock_redis)
        svc._settings.SESSION_IDLE_TIMEOUT_HOURS = 8
        svc._settings.MAX_CONCURRENT_SESSIONS_PER_USER = 0

        admin_user = _make_user()
        admin_user.role_obj = MagicMock()
        admin_user.role_obj.name = "Admin"
        admin_user.role_obj.permissions = ["query.submit"]
        mock_repo.get_by_username.return_value = admin_user

        mock_redis.zcard.return_value = 999

        profile, session_id = await svc.sign_in("admin", "secret")
        assert profile is not None
        mock_redis.zremrangebyrank.assert_not_called()

    @pytest.mark.asyncio
    async def test_max_sessions_one_allows_single_session(self, mock_repo, mock_redis):
        """MAX_CONCURRENT_SESSIONS_PER_USER=1 means only newest session kept."""
        svc = AuthService(mock_repo, mock_redis)
        svc._settings.SESSION_IDLE_TIMEOUT_HOURS = 8
        svc._settings.MAX_CONCURRENT_SESSIONS_PER_USER = 1

        admin_user = _make_user()
        admin_user.role_obj = MagicMock()
        admin_user.role_obj.name = "Admin"
        admin_user.role_obj.permissions = ["query.submit"]
        mock_repo.get_by_username.return_value = admin_user

        mock_redis.zcard.return_value = 2  # 1 existing + 1 new after zadd
        mock_redis.zrange.return_value = ["only-old-session"]

        profile, session_id = await svc.sign_in("admin", "secret")
        assert profile is not None
        zrange_calls = [c for c in mock_redis.zrange.call_args_list if "user_sessions:" in str(c[0][0])]
        assert len(zrange_calls) >= 1
        zrange_args = zrange_calls[-1][0]
        assert zrange_args[1] == 0
        assert zrange_args[2] == 0  # evict 1 (2 - 1 = 1)
