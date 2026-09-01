"""Unit tests for AuthService (T-048).

Tests sign-in with correct/incorrect credentials, session creation in Redis,
sign-out deletes session, and get_me returns profile; uses mocked repository and Redis.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError

from app.services.auth_service import AuthService

_USER_ID = "550e8400-e29b-41d4-a716-446655440000"
_ROLE_ID = "550e8400-e29b-41d4-a716-446655441000"


def _valid_session_record() -> dict:
    return {
        "user_id": _USER_ID,
        "username": "admin",
        "display_name": "Admin",
        "role": "admin",
        "role_id": _ROLE_ID,
        "role_name": "Admin",
        "permissions": ["query.submit"],
        "auth_provider": "local",
        "subject_id": "admin",
        "created_at": 1000.0,
        "last_activity": 1000.0,
    }


def _atomic_session_eval(*args):
    if args[1] == 4:
        return [1, 1, 0]
    if len(args) == 9:
        return args[8] or args[7]
    if len(args) == 6:
        return 1
    return [0, False, True, "", ""]


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
        redis.mget = AsyncMock(return_value=[None, None])
        redis.eval = AsyncMock(side_effect=_atomic_session_eval)
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

    @pytest.mark.asyncio
    async def test_sign_in_incorrect_credentials(self, service, mock_repo):
        mock_repo.get_by_username.return_value = None
        with pytest.raises(Exception) as exc_info:
            await service.sign_in("admin", "wrong")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_sign_out_deletes_session(self, service, mock_redis):
        await service.sign_out("session-123")
        mock_redis.eval.assert_awaited()

    @pytest.mark.asyncio
    async def test_get_me_returns_profile(self, service, mock_redis, mock_repo):
        mock_redis.mget.return_value = [json.dumps(_valid_session_record()), _USER_ID]
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
        mock_redis.mget.return_value = [json.dumps(_valid_session_record()), _USER_ID]
        mock_repo.get_by_id.return_value = None
        with pytest.raises(Exception) as exc_info:
            await service.get_me("session-123")
        assert exc_info.value.status_code == 401
        mock_redis.eval.assert_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "session_document",
        [
            pytest.param({**_valid_session_record(), "user_id": None}, id="null-user-id"),
            pytest.param(
                {**_valid_session_record(), "permissions": ["query.submit", ["nested"]]},
                id="invalid-nested-permission",
            ),
            pytest.param({**_valid_session_record(), "unknown": "field"}, id="unknown-field"),
        ],
    )
    async def test_get_me_corrupt_session_matches_middleware_contract(
        self,
        service,
        mock_redis,
        mock_repo,
        session_document,
    ):
        raw_session = json.dumps(session_document)
        mock_redis.mget.return_value = [raw_session, _USER_ID]

        with pytest.raises(HTTPException) as exc_info:
            await service.get_me("session-123")

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == {
            "error": "service_unavailable",
            "message_key": "error.service_unavailable",
        }
        mock_repo.get_by_id.assert_not_awaited()
        mock_redis.eval.assert_awaited()

    @pytest.mark.asyncio
    async def test_get_me_redis_outage_is_not_cleaned_as_corruption(self, service, mock_redis):
        dependency_error = RedisConnectionError("private dependency location")
        mock_redis.mget.side_effect = dependency_error

        with pytest.raises(RedisConnectionError):
            await service.get_me("session-123")

        mock_redis.eval.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_me_recovers_after_later_valid_session(self, service, mock_redis, mock_repo):
        corrupt_session = json.dumps({**_valid_session_record(), "permissions": {}})
        valid_session = json.dumps(_valid_session_record())
        mock_redis.mget.side_effect = [
            [corrupt_session, _USER_ID],
            [valid_session, _USER_ID],
        ]
        mock_repo.get_by_id.return_value = MagicMock(
            id=_USER_ID,
            username="admin",
            display_name="Admin",
            role="admin",
            role_obj=MagicMock(id=_ROLE_ID, name="Admin", permissions=["query.submit"]),
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.get_me("session-123")
        assert exc_info.value.status_code == 503

        profile = await service.get_me("session-123")
        assert profile.username == "admin"
