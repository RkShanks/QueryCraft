"""Real Redis regressions for atomic concurrent-session eviction."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import SessionMiddleware
from app.repositories import session_repository
from app.services.auth_service import AuthService


def _settings(max_sessions: int) -> SimpleNamespace:
    return SimpleNamespace(
        SESSION_IDLE_TIMEOUT_HOURS=8,
        MAX_CONCURRENT_SESSIONS_PER_USER=max_sessions,
    )


def _admin_user(user_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        username="admin",
        display_name="Admin",
        role="admin",
        password_hash="verified-by-test-boundary",
        auth_provider="local",
        role_id=None,
        role_obj=SimpleNamespace(name="Admin", permissions=["query.submit"]),
    )


async def _indexed_members(redis_client, user_id: str) -> list[str]:
    return list(await redis_client.zrange(f"user_sessions:{user_id}", 0, -1))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_equal_time_local_logins_keep_newest_linearized_session(redis_client):
    """Equal timestamp ordering follows Redis linearization, not session-id text."""
    user_id = "550e8400-e29b-41d4-a716-446655440111"
    repo = SimpleNamespace(get_by_username=AsyncMock(return_value=_admin_user(user_id)))
    auth_service = AuthService(repo, redis_client, settings=_settings(max_sessions=1))
    first_token = bytes([255]) * 32
    second_token = bytes([0]) * 32

    with (
        patch("app.services.auth_service.os.urandom", side_effect=[first_token, second_token]),
        patch("app.services.auth_service.time.time", side_effect=[1000.0, 1000.0, 1000.0, 1000.0]),
        patch("app.services.auth_service.verify_password", return_value=True),
    ):
        _, first_session_id = await auth_service.sign_in("admin", "secret")
        _, second_session_id = await auth_service.sign_in("admin", "secret")

    assert second_session_id < first_session_id
    assert await redis_client.exists(f"session:{second_session_id}") == 1
    assert await redis_client.exists(f"session:{first_session_id}") == 0
    assert await _indexed_members(redis_client, user_id) == [second_session_id]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stale_index_members_do_not_consume_capacity(redis_client):
    """Expired session keys are pruned before overflow selection."""
    user_id = "550e8400-e29b-41d4-a716-446655440222"
    repo = SimpleNamespace(get_by_username=AsyncMock(return_value=_admin_user(user_id)))
    auth_service = AuthService(repo, redis_client, settings=_settings(max_sessions=1))
    stale_session_id = "stale-index-member"
    live_session_id = "live-index-member"
    await redis_client.set(f"session:{live_session_id}", json.dumps({"user_id": user_id}), ex=3600)
    await redis_client.zadd(
        f"user_sessions:{user_id}",
        {
            live_session_id: 1000.0,
            stale_session_id: 9999999999.0,
        },
    )

    with (
        patch("app.services.auth_service.os.urandom", return_value=bytes([1]) * 32),
        patch("app.services.auth_service.time.time", side_effect=[2000.0, 2000.0]),
        patch("app.services.auth_service.verify_password", return_value=True),
    ):
        _, new_session_id = await auth_service.sign_in("admin", "secret")

    assert await redis_client.exists(f"session:{new_session_id}") == 1
    assert await redis_client.exists(f"session:{live_session_id}") == 0
    assert stale_session_id not in await _indexed_members(redis_client, user_id)
    assert await _indexed_members(redis_client, user_id) == [new_session_id]


class _EvictAfterReadRedis:
    def __init__(self, redis_client, session_id: str, user_id: str):
        self._redis = redis_client
        self._session_key = f"session:{session_id}"
        self._index_key = f"user_sessions:{user_id}"
        self._session_id = session_id

    def __getattr__(self, name: str):
        return getattr(self._redis, name)

    async def get(self, key: str):
        session_json = await self._redis.get(key)
        if key == self._session_key and session_json is not None:
            await self._redis.delete(self._session_key)
            await self._redis.zrem(self._index_key, self._session_id)
        return session_json


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_refresh_does_not_resurrect_concurrently_evicted_session(redis_client):
    """A blind refresh SET must not recreate a session deleted after read."""
    user_id = "550e8400-e29b-41d4-a716-446655440333"
    session_id = "old-refresh-session"
    await redis_client.set(
        f"session:{session_id}",
        json.dumps({"user_id": user_id, "last_activity": 1000.0}),
        ex=3600,
    )
    await redis_client.zadd(f"user_sessions:{user_id}", {session_id: 1000.0})
    middleware = SessionMiddleware(lambda *_: None, "redis://unused", idle_timeout_hours=8)
    middleware._redis = _EvictAfterReadRedis(redis_client, session_id, user_id)

    with patch("app.core.security.time.time", return_value=1001.0):
        loaded_session = await middleware._load_session(session_id)

    assert loaded_session is None
    assert await redis_client.exists(f"session:{session_id}") == 0
    assert await _indexed_members(redis_client, user_id) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sign_out_removes_empty_index_and_sequence(redis_client):
    """Deleting the final session removes both user index and sequence state."""
    user_id = "550e8400-e29b-41d4-a716-446655440444"
    session_id = "sign-out-session"
    repo = SimpleNamespace(get_by_username=AsyncMock(return_value=_admin_user(user_id)))
    auth_service = AuthService(repo, redis_client, settings=_settings(max_sessions=1))
    await redis_client.set(
        f"session:{session_id}",
        json.dumps({"user_id": user_id, "username": "admin"}),
        ex=3600,
    )
    await redis_client.zadd(f"user_sessions:{user_id}", {session_id: 1000.0})
    await redis_client.set(f"user_sessions_seq:{user_id}", "8", ex=3600)

    await auth_service.sign_out(session_id)

    assert await redis_client.exists(f"session:{session_id}") == 0
    assert await redis_client.exists(f"user_sessions:{user_id}") == 0
    assert await redis_client.exists(f"user_sessions_seq:{user_id}") == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_duplicate_atomic_session_creation_is_idempotent(redis_client):
    """Retrying one session creation leaves one key and one matching member."""
    request_type = session_repository.IndexedSessionCreateRequest
    user_id = "550e8400-e29b-41d4-a716-446655440555"
    session_id = "duplicate-create-session"
    payload = json.dumps({"user_id": user_id, "created_at": 1000.0, "last_activity": 1000.0})
    request = request_type(
        user_id=user_id,
        session_id=session_id,
        session_json=payload,
        created_at=1000.0,
        max_sessions=5,
        ttl_seconds=3600,
    )

    await asyncio.gather(
        session_repository.SessionRepository.create_indexed_session(redis_client, request),
        session_repository.SessionRepository.create_indexed_session(redis_client, request),
    )

    assert await redis_client.exists(f"session:{session_id}") == 1
    assert await _indexed_members(redis_client, user_id) == [session_id]
    assert await redis_client.exists(f"user_sessions_seq:{user_id}") == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simultaneous_equal_time_atomic_writes_keep_linearized_newest(redis_client):
    """Concurrent equal-time writes keep sessions with the highest Redis sequence."""
    request_type = session_repository.IndexedSessionCreateRequest
    user_id = "550e8400-e29b-41d4-a716-446655440666"
    session_ids = [f"simultaneous-session-{index}" for index in range(8)]

    async def create_session(session_id: str):
        await ready.wait()
        return await session_repository.SessionRepository.create_indexed_session(
            redis_client,
            request_type(
                user_id=user_id,
                session_id=session_id,
                session_json=json.dumps({"user_id": user_id, "created_at": 1000.0, "last_activity": 1000.0}),
                created_at=1000.0,
                max_sessions=3,
                ttl_seconds=3600,
            ),
        )

    ready = asyncio.Event()
    tasks = [asyncio.create_task(create_session(session_id)) for session_id in session_ids]
    ready.set()
    write_results = await asyncio.gather(*tasks)

    expected_live = [
        write_result.session_id for write_result in sorted(write_results, key=lambda write_result: write_result.sequence)[-3:]
    ]
    assert await _indexed_members(redis_client, user_id) == expected_live
    assert sum(await redis_client.exists(f"session:{session_id}") for session_id in session_ids) == 3
