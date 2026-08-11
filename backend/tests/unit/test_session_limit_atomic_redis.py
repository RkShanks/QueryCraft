"""Real Redis regressions for atomic concurrent-session eviction."""

import asyncio
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from redis.exceptions import ResponseError

from app.core.dependencies import require_active_user
from app.core.security import SessionMiddleware
from app.db.models.role import Role
from app.db.models.user import User
from app.repositories import session_repository
from app.services.auth_service import AuthService

ROLE_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655441000")


def _settings(max_sessions: int) -> SimpleNamespace:
    return SimpleNamespace(
        SESSION_IDLE_TIMEOUT_HOURS=8,
        MAX_CONCURRENT_SESSIONS_PER_USER=max_sessions,
    )


def _admin_user(user_id: str | uuid.UUID) -> User:
    user = User(
        id=uuid.UUID(str(user_id)),
        username="admin",
        display_name="Admin",
        role="admin",
        password_hash="verified-by-test-boundary",
        auth_provider="local",
        role_id=None,
    )
    user.role_obj = Role(id=ROLE_ID, name="Admin", permissions=["query.submit"])
    return user


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

    async def eval(self, script: str, numkeys: int, *keys_and_args: str):
        if keys_and_args and keys_and_args[0] == self._session_key:
            await self._redis.delete(self._session_key)
            await self._redis.zrem(self._index_key, self._session_id)
        return await self._redis.eval(script, numkeys, *keys_and_args)


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
async def test_refresh_cas_mismatch_does_not_overwrite_newer_session_payload(redis_client):
    """A stale read-modify-write refresh must not replace newer session JSON."""
    user_id = "550e8400-e29b-41d4-a716-446655440445"
    session_id = "cas-refresh-session"
    stale_payload = json.dumps(
        {"user_id": user_id, "last_activity": 1000.0, "permissions": ["query.submit"], "generation": 1}
    )
    current_payload = json.dumps(
        {
            "user_id": user_id,
            "last_activity": 1002.0,
            "permissions": ["admin.roles.manage"],
            "generation": 2,
            "auth_provider": "local",
        }
    )
    stale_replacement = json.dumps(
        {"user_id": user_id, "last_activity": 1000.0, "permissions": ["query.history.view"], "generation": 1}
    )
    await redis_client.set(f"session:{session_id}", current_payload, ex=3600)
    await redis_client.zadd(f"user_sessions:{user_id}", {session_id: 1000.0})
    await redis_client.set(f"user_sessions_seq:{user_id}", "1", ex=3600)

    refreshed = await session_repository.SessionRepository.refresh_indexed_session(
        redis_client,
        session_repository.IndexedSessionRefreshRequest(
            session_id=session_id,
            now=1003.0,
            ttl_seconds=3600,
            expected_session_json=stale_payload,
            replacement_session_json=stale_replacement,
        ),
    )

    refreshed_payload = json.loads(refreshed)
    stored_payload = json.loads(await redis_client.get(f"session:{session_id}"))
    assert refreshed_payload["permissions"] == ["query.history.view"]
    assert stored_payload["permissions"] == ["query.history.view"]
    assert stored_payload["auth_provider"] == "local"
    assert stored_payload["generation"] == 3


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
        write_result.session_id
        for write_result in sorted(write_results, key=lambda write_result: write_result.sequence)[-3:]
    ]
    assert await _indexed_members(redis_client, user_id) == expected_live
    live_key_counts = await asyncio.gather(
        *(redis_client.exists(f"session:{session_id}") for session_id in session_ids)
    )
    assert sum(live_key_counts) == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_new_login_ranks_after_legacy_high_score_session(redis_client):
    """Rollout compatibility: timestamp-scored indexes never outrank a fresh login."""
    request_type = session_repository.IndexedSessionCreateRequest
    user_id = "550e8400-e29b-41d4-a716-446655440777"
    legacy_session_id = "legacy-high-score-session"
    new_session_id = "new-after-legacy-session"
    await redis_client.set(f"session:{legacy_session_id}", json.dumps({"user_id": user_id}), ex=3600)
    await redis_client.zadd(f"user_sessions:{user_id}", {legacy_session_id: 999999999999999.0})

    result = await session_repository.SessionRepository.create_indexed_session(
        redis_client,
        request_type(
            user_id=user_id,
            session_id=new_session_id,
            session_json=json.dumps({"user_id": user_id, "created_at": 1.0, "last_activity": 1.0}),
            created_at=1.0,
            max_sessions=1,
            ttl_seconds=3600,
        ),
    )

    assert result.live_indexed_sessions == 1
    assert await _indexed_members(redis_client, user_id) == [new_session_id]
    assert await redis_client.exists(f"session:{legacy_session_id}") == 0
    assert await redis_client.exists(f"session:{new_session_id}") == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_different_users_index_and_sequence_state_remain_isolated(redis_client):
    """A session key cannot be re-indexed under another user."""
    request_type = session_repository.IndexedSessionCreateRequest
    user_a = "550e8400-e29b-41d4-a716-446655440888"
    user_b = "550e8400-e29b-41d4-a716-446655440889"
    session_id = "shared-session-id"
    await session_repository.SessionRepository.create_indexed_session(
        redis_client,
        request_type(
            user_id=user_a,
            session_id=session_id,
            session_json=json.dumps({"user_id": user_a, "created_at": 1000.0, "last_activity": 1000.0}),
            created_at=1000.0,
            max_sessions=5,
            ttl_seconds=3600,
        ),
    )

    with pytest.raises(ResponseError, match="session-user-mismatch"):
        await session_repository.SessionRepository.create_indexed_session(
            redis_client,
            request_type(
                user_id=user_b,
                session_id=session_id,
                session_json=json.dumps({"user_id": user_b, "created_at": 1001.0, "last_activity": 1001.0}),
                created_at=1001.0,
                max_sessions=5,
                ttl_seconds=3600,
            ),
        )

    assert await _indexed_members(redis_client, user_a) == [session_id]
    assert await redis_client.exists(f"user_sessions:{user_b}") == 0
    assert await redis_client.exists(f"user_sessions_seq:{user_b}") == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_extends_session_index_and_sequence_ttls(redis_client):
    """Index and sequence TTLs are refreshed with the active session TTL."""
    user_id = "550e8400-e29b-41d4-a716-446655440990"
    session_id = "ttl-refresh-session"
    await redis_client.set(
        f"session:{session_id}",
        json.dumps({"user_id": user_id, "last_activity": 1000.0}),
        ex=5,
    )
    await redis_client.zadd(f"user_sessions:{user_id}", {session_id: 1000.0})
    await redis_client.expire(f"user_sessions:{user_id}", 5)
    await redis_client.set(f"user_sessions_seq:{user_id}", "1", ex=5)

    refreshed = await session_repository.SessionRepository.refresh_indexed_session(
        redis_client,
        session_repository.IndexedSessionRefreshRequest(session_id=session_id, now=1001.0, ttl_seconds=3600),
    )

    assert refreshed is not None
    assert await redis_client.ttl(f"session:{session_id}") >= 3590
    assert await redis_client.ttl(f"user_sessions:{user_id}") >= 3590
    assert await redis_client.ttl(f"user_sessions_seq:{user_id}") >= 3590


@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_repairs_live_legacy_session_missing_index_state(redis_client):
    """Rollout repair keeps a live unindexed session consistent without resurrecting a missing key."""
    user_id = "550e8400-e29b-41d4-a716-446655440991"
    session_id = "legacy-live-unindexed-session"
    await redis_client.set(
        f"session:{session_id}",
        json.dumps({"user_id": user_id, "last_activity": 1000.0}),
        ex=3600,
    )

    refreshed = await session_repository.SessionRepository.refresh_indexed_session(
        redis_client,
        session_repository.IndexedSessionRefreshRequest(session_id=session_id, now=1001.0, ttl_seconds=3600),
    )

    assert refreshed is not None
    assert await _indexed_members(redis_client, user_id) == [session_id]
    assert await redis_client.exists(f"user_sessions_seq:{user_id}") == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_idle_expiry_removes_session_index_and_sequence(redis_client):
    """Idle expiry path removes session state and matching index state atomically."""
    user_id = "550e8400-e29b-41d4-a716-446655440992"
    session_id = "idle-expired-session"
    await redis_client.set(
        f"session:{session_id}",
        json.dumps({"user_id": user_id, "last_activity": 10.0}),
        ex=3600,
    )
    await redis_client.zadd(f"user_sessions:{user_id}", {session_id: 10.0})
    await redis_client.set(f"user_sessions_seq:{user_id}", "1", ex=3600)
    middleware = SessionMiddleware(lambda *_: None, "redis://unused", idle_timeout_hours=1)
    middleware._redis = redis_client

    with patch("app.core.security.time.time", return_value=4000.0):
        loaded = await middleware._load_session(session_id)

    assert loaded is None
    assert await redis_client.exists(f"session:{session_id}") == 0
    assert await redis_client.exists(f"user_sessions:{user_id}") == 0
    assert await redis_client.exists(f"user_sessions_seq:{user_id}") == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deleted_user_cleanup_removes_session_index_and_sequence(redis_client):
    """Stale-user dependency cleanup removes both the session and user index state."""
    user_id = "550e8400-e29b-41d4-a716-446655440993"
    session_id = "deleted-user-session"
    await redis_client.set(
        f"session:{session_id}",
        json.dumps({"user_id": user_id, "last_activity": 1000.0}),
        ex=3600,
    )
    await redis_client.zadd(f"user_sessions:{user_id}", {session_id: 1000.0})
    await redis_client.set(f"user_sessions_seq:{user_id}", "1", ex=3600)
    request = SimpleNamespace(state=SimpleNamespace(session={"user_id": user_id}, session_id=session_id))
    db_result = SimpleNamespace(scalar_one_or_none=lambda: None)
    db = SimpleNamespace(execute=AsyncMock(return_value=db_result))

    with pytest.raises(HTTPException) as exc_info:
        await require_active_user(request, db=db, redis=redis_client)

    assert exc_info.value.status_code == 401
    assert await redis_client.exists(f"session:{session_id}") == 0
    assert await redis_client.exists(f"user_sessions:{user_id}") == 0
    assert await redis_client.exists(f"user_sessions_seq:{user_id}") == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_local_login_failed_audit_rolls_back_session_index_and_sequence(redis_client):
    """A failed durable audit revokes the just-created local login session."""
    user_id = "550e8400-e29b-41d4-a716-446655440994"
    repo = SimpleNamespace(get_by_username=AsyncMock(return_value=_admin_user(user_id)))
    auth_service = AuthService(repo, redis_client, settings=_settings(max_sessions=5))

    with (
        patch("app.services.auth_service.os.urandom", return_value=bytes([7]) * 32),
        patch("app.services.auth_service.time.time", side_effect=[1000.0, 1000.0]),
        patch("app.services.auth_service.verify_password", return_value=True),
        patch("app.services.auth_service.AuditService.log", side_effect=RuntimeError("audit unavailable")),
        pytest.raises(RuntimeError, match="audit unavailable"),
    ):
        await auth_service.sign_in("admin", "secret", db_session=AsyncMock())

    session_id = (bytes([7]) * 32).hex()
    assert await redis_client.exists(f"session:{session_id}") == 0
    assert await redis_client.exists(f"user_sessions:{user_id}") == 0
    assert await redis_client.exists(f"user_sessions_seq:{user_id}") == 0
