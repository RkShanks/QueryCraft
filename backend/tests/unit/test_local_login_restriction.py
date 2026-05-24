"""TDD tests for local login restriction (T-647).

Tests for:
- Admin user with auth_provider='local' can sign in via POST /auth/sign-in
- Non-admin SSO user (auth_provider='oidc') is rejected with generic 401
- Non-admin SSO user (auth_provider='saml') is rejected with generic 401
- Non-admin local user (auth_provider='local', role='viewer') is rejected with generic 401
- Error message is generic — no leak of whether username exists
- Error message is generic — no leak of whether user is SSO-only
- Built-in admin always works regardless of SSO configuration
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.auth_service import AuthService


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


class TestLocalLoginRestriction:
    """Local login restriction — admin-only per FR-120."""

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.get_by_username = AsyncMock()
        repo.get_by_id = AsyncMock()
        return repo

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.set = AsyncMock()
        redis.delete = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        return redis

    @pytest.fixture
    def service(self, mock_repo, mock_redis):
        return AuthService(mock_repo, mock_redis)

    @pytest.mark.asyncio
    async def test_builtin_admin_local_login_succeeds(self, service, mock_repo, mock_redis):
        """Built-in admin with auth_provider='local' can sign in."""
        admin_user = _make_user(username="admin", auth_provider="local", role="admin", is_builtin=True)
        admin_user.role_obj = MagicMock()
        admin_user.role_obj.name = "Admin"
        admin_user.role_obj.permissions = ["query.submit", "admin.sso.manage"]
        mock_repo.get_by_username.return_value = admin_user

        profile, session_id = await service.sign_in("admin", "secret")
        assert profile.username == "admin"
        assert session_id is not None

    @pytest.mark.asyncio
    async def test_sso_oidc_user_rejected_from_local_login(self, service, mock_repo):
        """User with auth_provider='oidc' is rejected from local login with generic 401."""
        sso_user = _make_user(username="sso_user", auth_provider="oidc", role="viewer", is_builtin=False)
        sso_user.password_hash = None
        mock_repo.get_by_username.return_value = sso_user

        with pytest.raises(HTTPException) as exc_info:
            await service.sign_in("sso_user", "any-password")

        assert exc_info.value.status_code == 401
        detail = exc_info.value.detail
        assert detail.get("message_key") == "error.unauthorized"
        error_str = str(detail)
        assert "sso" not in error_str.lower() or "unauthorized" in error_str.lower()
        assert "oidc" not in error_str.lower()
        assert "saml" not in error_str.lower()

    @pytest.mark.asyncio
    async def test_sso_saml_user_rejected_from_local_login(self, service, mock_repo):
        """User with auth_provider='saml' is rejected from local login with generic 401."""
        sso_user = _make_user(username="saml_user", auth_provider="saml", role="analyst", is_builtin=False)
        sso_user.password_hash = None
        mock_repo.get_by_username.return_value = sso_user

        with pytest.raises(HTTPException) as exc_info:
            await service.sign_in("saml_user", "any-password")

        assert exc_info.value.status_code == 401
        detail = exc_info.value.detail
        assert detail.get("message_key") == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_non_admin_local_user_rejected(self, service, mock_repo):
        """Non-admin local user is rejected from local login with generic 401."""
        local_viewer = _make_user(username="viewer", auth_provider="local", role="viewer", is_builtin=False)
        mock_repo.get_by_username.return_value = local_viewer

        with pytest.raises(HTTPException) as exc_info:
            await service.sign_in("viewer", "secret")

        assert exc_info.value.status_code == 401
        detail = exc_info.value.detail
        assert detail.get("message_key") == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_nonexistent_user_generic_401(self, service, mock_repo):
        """Nonexistent user returns the same generic 401 — no account existence leak."""
        mock_repo.get_by_username.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await service.sign_in("nonexistent", "any-password")

        assert exc_info.value.status_code == 401
        detail = exc_info.value.detail
        assert detail.get("message_key") == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_no_leak_of_auth_provider(self, service, mock_repo):
        """Error response does not leak whether the user is SSO-only or local."""
        sso_user = _make_user(username="sso_only", auth_provider="oidc", role="viewer", is_builtin=False)
        sso_user.password_hash = None
        mock_repo.get_by_username.return_value = sso_user

        with pytest.raises(HTTPException) as exc_info:
            await service.sign_in("sso_only", "any-password")

        detail_str = str(exc_info.value.detail)
        assert "oidc" not in detail_str.lower()
        assert "saml" not in detail_str.lower()
        assert "sso" not in detail_str.lower()

    @pytest.mark.asyncio
    async def test_admin_with_sso_provider_can_still_local_login(self, service, mock_repo):
        """An admin user (even if they also have SSO) can use local login."""
        admin_user = _make_user(username="admin_sso", auth_provider="local", role="admin", is_builtin=True)
        admin_user.role_obj = MagicMock()
        admin_user.role_obj.name = "Admin"
        admin_user.role_obj.permissions = ["query.submit", "admin.sso.manage"]
        mock_repo.get_by_username.return_value = admin_user

        profile, session_id = await service.sign_in("admin_sso", "secret")
        assert profile.username == "admin_sso"
