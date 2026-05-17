"""Unit tests for AuthService (T-048).

Tests sign-in with correct/incorrect credentials, session creation in Redis,
sign-out deletes session, and get_me returns profile; uses mocked repository and Redis.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.auth_service import AuthService


class TestAuthService:
    """AuthService unit tests with mocked dependencies."""

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
    async def test_sign_in_correct_credentials(self, service, mock_repo, mock_redis):
        from app.core.security import hash_password

        mock_repo.get_by_username.return_value = MagicMock(
            id="550e8400-e29b-41d4-a716-446655440000",
            username="admin",
            display_name="Admin",
            role="admin",
            password_hash=hash_password("secret"),
        )
        profile, session_id = await service.sign_in("admin", "secret")
        assert profile.username == "admin"
        assert session_id is not None
        mock_redis.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sign_in_incorrect_credentials(self, service, mock_repo):
        mock_repo.get_by_username.return_value = None
        with pytest.raises(Exception) as exc_info:
            await service.sign_in("admin", "wrong")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_sign_out_deletes_session(self, service, mock_redis):
        await service.sign_out("session-123")
        mock_redis.delete.assert_awaited_once_with("session:session-123")

    @pytest.mark.asyncio
    async def test_get_me_returns_profile(self, service, mock_redis, mock_repo):
        mock_redis.get.return_value = (
            '{"user_id": "550e8400-e29b-41d4-a716-446655440000",'
            ' "username": "admin", "display_name": "Admin", "role": "admin"}'
        )
        mock_repo.get_by_id.return_value = MagicMock(
            id="550e8400-e29b-41d4-a716-446655440000",
            username="admin",
            display_name="Admin",
            role="admin",
        )
        profile = await service.get_me("session-123")
        assert profile.username == "admin"

    @pytest.mark.asyncio
    async def test_get_me_stale_session_deletes_key_and_raises_401(self, service, mock_redis, mock_repo):
        """Stale Redis session (user_id absent from DB) deletes key and raises 401."""
        mock_redis.get.return_value = (
            '{"user_id": "550e8400-e29b-41d4-a716-446655440000",'
            ' "username": "admin", "display_name": "Admin", "role": "admin"}'
        )
        mock_repo.get_by_id.return_value = None
        with pytest.raises(Exception) as exc_info:
            await service.get_me("session-123")
        assert exc_info.value.status_code == 401
        mock_redis.delete.assert_awaited_once_with("session:session-123")
