"""TDD tests for extended session profile data (T-631).

Real Redis sign-in payload storage is covered by concurrent-session tests.
This module verifies get_me returns extended UserProfile fields.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.auth_service import AuthService


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
        redis.eval = AsyncMock(side_effect=lambda *args: [1, 1, 0] if args[1] == 3 else args[7])
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
        role.id = "role-uuid-1234"
        role.name = "Analyst"
        role.permissions = ["query.submit", "query.history.view"]

        user = MagicMock()
        user.id = "550e8400-e29b-41d4-a716-446655440000"
        user.username = "analyst1"
        user.display_name = "Analyst One"
        user.role = "admin"
        user.role_id = "role-uuid-1234"
        user.auth_provider = "local"
        user.password_hash = hash_password("secret")
        user.role_obj = role
        return user

    @pytest.mark.asyncio
    async def test_get_me_returns_extended_profile(self, service, mock_repo, mock_redis, user_with_role):
        """get_me returns UserProfile with role_id, role_name, permissions, auth_provider."""
        mock_redis.get.return_value = json.dumps(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "username": "analyst1",
                "display_name": "Analyst One",
                "role": "analyst",
                "role_id": "role-uuid-1234",
                "role_name": "Analyst",
                "permissions": ["query.submit", "query.history.view"],
                "auth_provider": "local",
                "subject_id": "analyst1",
                "email": "analyst1@example.com",
            }
        )
        mock_repo.get_by_id.return_value = user_with_role
        profile = await service.get_me("session-123")
        assert profile.role_id == "role-uuid-1234"
        assert profile.role_name == "Analyst"
        assert profile.permissions == ["query.submit", "query.history.view"]
        assert profile.auth_provider == "local"

    @pytest.mark.asyncio
    async def test_get_me_user_without_role(self, service, mock_repo, mock_redis):
        """User with no role_id returns None for role fields."""
        user_no_role = MagicMock()
        user_no_role.id = "550e8400-e29b-41d4-a716-446655440000"
        user_no_role.username = "unmapped"
        user_no_role.display_name = "Unmapped User"
        user_no_role.role = "user"
        user_no_role.role_id = None
        user_no_role.auth_provider = "oidc"
        user_no_role.role_obj = None

        mock_redis.get.return_value = json.dumps(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "username": "unmapped",
                "display_name": "Unmapped User",
                "role": "user",
                "role_id": None,
                "role_name": None,
                "permissions": [],
                "auth_provider": "oidc",
                "subject_id": "sso-subject-123",
            }
        )
        mock_repo.get_by_id.return_value = user_no_role
        profile = await service.get_me("session-123")
        assert profile.role_id is None
        assert profile.role_name is None
        assert profile.permissions == []
        assert profile.auth_provider == "oidc"

    @pytest.mark.asyncio
    async def test_profile_response_does_not_expose_password_hash(self, service, mock_repo, mock_redis, user_with_role):
        """UserProfile must never contain password_hash or other secrets."""
        mock_redis.get.return_value = json.dumps(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "username": "analyst1",
                "display_name": "Analyst One",
                "role": "analyst",
                "role_id": "role-uuid-1234",
                "role_name": "Analyst",
                "permissions": ["query.submit"],
                "auth_provider": "local",
                "subject_id": "analyst1",
                "password_hash": "should_not_appear",  # simulate old session with this field
            }
        )
        mock_repo.get_by_id.return_value = user_with_role
        profile = await service.get_me("session-123")
        profile_dict = profile.model_dump()
        assert "password_hash" not in profile_dict
        assert "password" not in profile_dict
