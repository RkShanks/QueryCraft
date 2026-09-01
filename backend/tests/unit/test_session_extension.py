"""TDD tests for extended session profile data (T-631).

Real Redis sign-in payload storage is covered by concurrent-session tests.
This module verifies get_me returns extended UserProfile fields.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.auth_service import AuthService

_USER_ID = "550e8400-e29b-41d4-a716-446655440000"
_ROLE_ID = "550e8400-e29b-41d4-a716-446655441000"


def _session_record(**updates) -> dict:
    session = {
        "user_id": _USER_ID,
        "username": "analyst1",
        "display_name": "Analyst One",
        "role": "analyst",
        "role_id": _ROLE_ID,
        "role_name": "Analyst",
        "permissions": ["query.submit", "query.history.view"],
        "auth_provider": "local",
        "subject_id": "analyst1",
        "created_at": 1000.0,
        "last_activity": 1000.0,
    }
    session.update(updates)
    return session


class TestSessionExtension:
    """Extended session field tests for Phase 5 SSO/RBAC."""

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
        redis.mget = AsyncMock(return_value=[None, None])
        redis.eval = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def service(self, mock_repo, mock_redis):
        return AuthService(mock_repo, mock_redis)

    @pytest.fixture
    def user_with_role(self):
        """Return a mock admin user with role relationship populated.

        Local login is admin-only (FR-120), so test users must be admins.
        """
        from app.core.security import hash_password

        role = MagicMock()
        role.id = _ROLE_ID
        role.name = "Analyst"
        role.permissions = ["query.submit", "query.history.view"]

        user = MagicMock()
        user.id = _USER_ID
        user.username = "analyst1"
        user.display_name = "Analyst One"
        user.role = "admin"
        user.role_id = _ROLE_ID
        user.auth_provider = "local"
        user.password_hash = hash_password("secret")
        user.role_obj = role
        return user

    @pytest.mark.asyncio
    async def test_get_me_returns_extended_profile(self, service, mock_repo, mock_redis, user_with_role):
        """get_me returns UserProfile with role_id, role_name, permissions, auth_provider."""
        mock_redis.mget.return_value = [
            json.dumps(_session_record(email="analyst1@example.com")),
            _USER_ID,
        ]
        mock_repo.get_by_id.return_value = user_with_role
        profile = await service.get_me("session-123")
        assert profile.role_id == _ROLE_ID
        assert profile.role_name == "Analyst"
        assert profile.permissions == ["query.submit", "query.history.view"]
        assert profile.auth_provider == "local"

    @pytest.mark.asyncio
    async def test_get_me_user_without_role(self, service, mock_repo, mock_redis):
        """User with no role_id returns None for role fields."""
        user_no_role = MagicMock()
        user_no_role.id = _USER_ID
        user_no_role.username = "unmapped"
        user_no_role.display_name = "Unmapped User"
        user_no_role.role = "user"
        user_no_role.role_id = None
        user_no_role.auth_provider = "oidc"
        user_no_role.role_obj = None

        mock_redis.mget.return_value = [
            json.dumps(
                _session_record(
                    username="unmapped",
                    display_name="Unmapped User",
                    role="user",
                    role_id=None,
                    role_name=None,
                    permissions=[],
                    auth_provider="oidc",
                    subject_id="sso-subject-123",
                )
            ),
            _USER_ID,
        ]
        mock_repo.get_by_id.return_value = user_no_role
        profile = await service.get_me("session-123")
        assert profile.role_id is None
        assert profile.role_name is None
        assert profile.permissions == []
        assert profile.auth_provider == "oidc"

    @pytest.mark.asyncio
    async def test_unknown_sensitive_session_field_is_rejected(self, service, mock_repo, mock_redis):
        """Unexpected persisted fields never reach a profile response."""
        raw_session = json.dumps(_session_record(password_hash="should_not_appear"))
        mock_redis.mget.return_value = [raw_session, _USER_ID]

        with pytest.raises(HTTPException) as exc_info:
            await service.get_me("session-123")

        assert exc_info.value.status_code == 503
        mock_repo.get_by_id.assert_not_awaited()
        mock_redis.eval.assert_awaited()
