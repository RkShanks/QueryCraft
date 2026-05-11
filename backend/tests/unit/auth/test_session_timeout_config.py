"""T-213: Session timeout reads from settings.

Test-first: AuthService.sign_in() must use settings.SESSION_IDLE_TIMEOUT_HOURS
instead of a hardcoded 8-hour value.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.auth_service import AuthService


class TestSessionTimeoutConfig:
    """Unit tests for session idle timeout configurability."""

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.get_by_username = AsyncMock()
        return repo

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.set = AsyncMock()
        return redis

    @pytest.fixture
    def mock_user(self):
        from app.core.security import hash_password

        return MagicMock(
            id="550e8400-e29b-41d4-a716-446655440000",
            username="admin",
            display_name="Admin",
            role="admin",
            password_hash=hash_password("secret"),
        )

    @pytest.mark.asyncio
    async def test_sign_in_uses_configured_timeout(self, mock_repo, mock_redis, mock_user):
        """When SESSION_IDLE_TIMEOUT_HOURS=2, Redis SET ex=7200."""
        mock_repo.get_by_username.return_value = mock_user
        settings = MagicMock()
        settings.SESSION_IDLE_TIMEOUT_HOURS = 2

        service = AuthService(mock_repo, mock_redis, settings=settings)
        await service.sign_in("admin", "secret")

        mock_redis.set.assert_awaited_once()
        call_args = mock_redis.set.await_args
        assert call_args.kwargs["ex"] == 7200  # 2 * 3600

    @pytest.mark.asyncio
    async def test_sign_in_uses_default_timeout(self, mock_repo, mock_redis, mock_user):
        """When SESSION_IDLE_TIMEOUT_HOURS=8, Redis SET ex=28800."""
        mock_repo.get_by_username.return_value = mock_user
        settings = MagicMock()
        settings.SESSION_IDLE_TIMEOUT_HOURS = 8

        service = AuthService(mock_repo, mock_redis, settings=settings)
        await service.sign_in("admin", "secret")

        mock_redis.set.assert_awaited_once()
        call_args = mock_redis.set.await_args
        assert call_args.kwargs["ex"] == 28800  # 8 * 3600
