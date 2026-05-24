"""TDD tests for extended Redis session data (T-631).

Verifies AuthService.sign_in stores role_id, role_name, permissions,
auth_provider, subject_id in Redis session. Verifies get_me returns
extended UserProfile with new fields.
"""

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
        return redis

    @pytest.fixture
    def service(self, mock_repo, mock_redis):
        return AuthService(mock_repo, mock_redis)

    @pytest.fixture
    def user_with_role(self):
        """Return a mock user with role relationship populated."""
        from app.core.security import hash_password

        role = MagicMock()
        role.id = "role-uuid-1234"
        role.name = "Analyst"
        role.permissions = ["query.submit", "query.history.view"]

        user = MagicMock()
        user.id = "550e8400-e29b-41d4-a716-446655440000"
        user.username = "analyst1"
        user.display_name = "Analyst One"
        user.role = "analyst"
        user.role_id = "role-uuid-1234"
        user.auth_provider = "local"
        user.password_hash = hash_password("secret")
        user.role_obj = role
        return user

    @pytest.mark.asyncio
    async def test_sign_in_stores_role_id_in_session(self, service, mock_repo, mock_redis, user_with_role):
        """Session must contain role_id from user.role_id."""
        mock_repo.get_by_username.return_value = user_with_role
        profile, session_id = await service.sign_in("analyst1", "secret")
        call_args = mock_redis.set.await_args
        session_data = call_args[0][0]  # first positional arg is key
        # Actually redis.set(key, value, ex=...), so value is second arg
        raw_value = call_args[0][1]
        import json
        session = json.loads(raw_value)
        assert session["role_id"] == "role-uuid-1234"

    @pytest.mark.asyncio
    async def test_sign_in_stores_role_name_in_session(self, service, mock_repo, mock_redis, user_with_role):
        """Session must contain role_name from user.role_obj.name."""
        mock_repo.get_by_username.return_value = user_with_role
        profile, session_id = await service.sign_in("analyst1", "secret")
        call_args = mock_redis.set.await_args
        raw_value = call_args[0][1]
        import json
        session = json.loads(raw_value)
        assert session["role_name"] == "Analyst"

    @pytest.mark.asyncio
    async def test_sign_in_stores_permissions_in_session(self, service, mock_repo, mock_redis, user_with_role):
        """Session must contain permissions list from role."""
        mock_repo.get_by_username.return_value = user_with_role
        profile, session_id = await service.sign_in("analyst1", "secret")
        call_args = mock_redis.set.await_args
        raw_value = call_args[0][1]
        import json
        session = json.loads(raw_value)
        assert session["permissions"] == ["query.submit", "query.history.view"]

    @pytest.mark.asyncio
    async def test_sign_in_stores_auth_provider_in_session(self, service, mock_repo, mock_redis, user_with_role):
        """Session must contain auth_provider from user.auth_provider."""
        mock_repo.get_by_username.return_value = user_with_role
        profile, session_id = await service.sign_in("analyst1", "secret")
        call_args = mock_redis.set.await_args
        raw_value = call_args[0][1]
        import json
        session = json.loads(raw_value)
        assert session["auth_provider"] == "local"

    @pytest.mark.asyncio
    async def test_sign_in_stores_subject_id_for_local_user(self, service, mock_repo, mock_redis, user_with_role):
        """Local users: subject_id defaults to username."""
        mock_repo.get_by_username.return_value = user_with_role
        profile, session_id = await service.sign_in("analyst1", "secret")
        call_args = mock_redis.set.await_args
        raw_value = call_args[0][1]
        import json
        session = json.loads(raw_value)
        assert session["subject_id"] == "analyst1"

    @pytest.mark.asyncio
    async def test_sign_in_preserves_existing_fields(self, service, mock_repo, mock_redis, user_with_role):
        """Existing session fields (user_id, username, display_name, role, created_at, last_activity) are preserved."""
        mock_repo.get_by_username.return_value = user_with_role
        profile, session_id = await service.sign_in("analyst1", "secret")
        call_args = mock_redis.set.await_args
        raw_value = call_args[0][1]
        import json
        session = json.loads(raw_value)
        assert session["user_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert session["username"] == "analyst1"
        assert session["display_name"] == "Analyst One"
        assert session["role"] == "analyst"
        assert "created_at" in session
        assert "last_activity" in session

    @pytest.mark.asyncio
    async def test_get_me_returns_extended_profile(self, service, mock_repo, mock_redis, user_with_role):
        """get_me returns UserProfile with role_id, role_name, permissions, auth_provider."""
        import json
        mock_redis.get.return_value = json.dumps({
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
        })
        mock_repo.get_by_id.return_value = user_with_role
        profile = await service.get_me("session-123")
        assert profile.role_id == "role-uuid-1234"
        assert profile.role_name == "Analyst"
        assert profile.permissions == ["query.submit", "query.history.view"]
        assert profile.auth_provider == "local"

    @pytest.mark.asyncio
    async def test_get_me_user_without_role(self, service, mock_repo, mock_redis):
        """User with no role_id returns None for role fields."""
        import json
        user_no_role = MagicMock()
        user_no_role.id = "550e8400-e29b-41d4-a716-446655440000"
        user_no_role.username = "unmapped"
        user_no_role.display_name = "Unmapped User"
        user_no_role.role = "user"
        user_no_role.role_id = None
        user_no_role.auth_provider = "oidc"
        user_no_role.role_obj = None

        mock_redis.get.return_value = json.dumps({
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "username": "unmapped",
            "display_name": "Unmapped User",
            "role": "user",
            "role_id": None,
            "role_name": None,
            "permissions": [],
            "auth_provider": "oidc",
            "subject_id": "sso-subject-123",
        })
        mock_repo.get_by_id.return_value = user_no_role
        profile = await service.get_me("session-123")
        assert profile.role_id is None
        assert profile.role_name is None
        assert profile.permissions == []
        assert profile.auth_provider == "oidc"

    @pytest.mark.asyncio
    async def test_profile_response_does_not_expose_password_hash(self, service, mock_repo, mock_redis, user_with_role):
        """UserProfile must never contain password_hash or other secrets."""
        import json
        mock_redis.get.return_value = json.dumps({
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
        })
        mock_repo.get_by_id.return_value = user_with_role
        profile = await service.get_me("session-123")
        profile_dict = profile.model_dump()
        assert "password_hash" not in profile_dict
        assert "password" not in profile_dict
