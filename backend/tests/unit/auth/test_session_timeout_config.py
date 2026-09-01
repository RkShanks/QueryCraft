"""T-213: Session timeout reads from settings.

Test-first: AuthService.sign_in() must use settings.SESSION_IDLE_TIMEOUT_HOURS
instead of a hardcoded 8-hour value.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.auth_service import AuthService


def _atomic_session_eval(*args):
    return [1, 1, 0] if args[1] == 4 else [0, False, True, "", ""]


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
        redis.eval = AsyncMock(side_effect=_atomic_session_eval)
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
        """When SESSION_IDLE_TIMEOUT_HOURS=2, atomic creation receives TTL 7200."""
        mock_repo.get_by_username.return_value = mock_user
        settings = MagicMock()
        settings.SESSION_IDLE_TIMEOUT_HOURS = 2

        service = AuthService(mock_repo, mock_redis, settings=settings)
        await service.sign_in("admin", "secret")

        create_call = mock_redis.eval.await_args.args
        assert create_call[1] == 4
        assert create_call[10] == "7200"

    @pytest.mark.asyncio
    async def test_sign_in_uses_default_timeout(self, mock_repo, mock_redis, mock_user):
        """When SESSION_IDLE_TIMEOUT_HOURS=8, atomic creation receives TTL 28800."""
        mock_repo.get_by_username.return_value = mock_user
        settings = MagicMock()
        settings.SESSION_IDLE_TIMEOUT_HOURS = 8

        service = AuthService(mock_repo, mock_redis, settings=settings)
        await service.sign_in("admin", "secret")

        create_call = mock_redis.eval.await_args.args
        assert create_call[1] == 4
        assert create_call[10] == "28800"
