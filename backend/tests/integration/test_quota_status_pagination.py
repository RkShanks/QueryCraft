"""CHUNK-12 quota-status pagination and batching regressions."""

import asyncio
import math
import uuid
from collections import Counter
from collections.abc import AsyncGenerator, Sequence
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.api.dependencies.permissions import get_current_role
from app.api.v1.admin_quotas import router
from app.core.dependencies import get_db, get_redis
from app.db.base import get_db as get_permission_db
from app.db.models.enums import Permission

_ROLE_COUNT = 120
_USERS_PER_ROLE = 25
_ROLE_PAGE_LIMIT = 50
_USER_BATCH_LIMIT = 500
_REDIS_BATCH_LIMIT = 500


class RecordingQuotaRedis:
    """Record batch sizes and dimensions while delegating to real Redis."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self.get_calls = 0
        self.mget_sizes: list[int] = []
        self.dimensions: Counter[str] = Counter()

    async def get(self, key: str):
        self.get_calls += 1
        self.dimensions[key.split(":")[2]] += 1
        return await self._redis.get(key)

    async def mget(self, keys: Sequence[str]):
        self.mget_sizes.append(len(keys))
        self.dimensions.update(key.split(":")[2] for key in keys)
        return await self._redis.mget(keys)


class StaticCounterRedis(RecordingQuotaRedis):
    def __init__(self, redis: Redis, counter_value: str) -> None:
        super().__init__(redis)
        self._counter_value = counter_value

    async def mget(self, keys: Sequence[str]):
        self.mget_sizes.append(len(keys))
        self.dimensions.update(key.split(":")[2] for key in keys)
        return [self._counter_value] * len(keys)


class FailingBatchRedis(RecordingQuotaRedis):
    async def mget(self, keys: Sequence[str]):
        self.mget_sizes.append(len(keys))
        raise RedisConnectionError("quota status batch unavailable")


class UnexpectedFailingBatchRedis(RecordingQuotaRedis):
    async def mget(self, keys: Sequence[str]):
        self.mget_sizes.append(len(keys))
        raise RuntimeError("unexpected quota status batch failure")


class BlockingBatchRedis(RecordingQuotaRedis):
    def __init__(self, redis: Redis) -> None:
        super().__init__(redis)
        self.started = asyncio.Event()

    async def mget(self, keys: Sequence[str]):
        self.mget_sizes.append(len(keys))
        self.started.set()
        await asyncio.Event().wait()


async def _quota_status_client(
    db_session: AsyncSession,
    redis: RecordingQuotaRedis,
    user_id: uuid.UUID,
    role_access: tuple[uuid.UUID, list[str]],
) -> AsyncGenerator[AsyncClient, None]:
    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_role() -> tuple[uuid.UUID, str, list[str]]:
        role_id, permissions = role_access
        return role_id, "Quota Test Admin", permissions

    async def override_redis() -> RecordingQuotaRedis:
        return redis

    app = FastAPI()

    @app.middleware("http")
    async def attach_session(request: Request, call_next):
        request.state.session = {"user_id": str(user_id)}
        return await call_next(request)

    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_permission_db] = override_db
    app.dependency_overrides[get_current_role] = override_role
    app.dependency_overrides[get_redis] = override_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def _seed_quota_status_dataset(
    db_session: AsyncSession,
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    await db_session.execute(text("DELETE FROM role_quotas"))
    role_ids = [uuid.UUID(int=200_000 + index) for index in range(_ROLE_COUNT)]
    await db_session.execute(
        text(
            """
            INSERT INTO roles (id, name, description, priority, permissions, is_builtin)
            VALUES (:id, :name, '', :priority, '[]'::jsonb, false)
            """
        ),
        [
            {"id": role_id, "name": f"Chunk12 Role {index:03d}", "priority": 50_000 + index}
            for index, role_id in enumerate(role_ids)
        ],
    )
    await db_session.execute(
        text(
            """
            INSERT INTO role_quotas (
                id, role_id, daily_query_limit,
                daily_execution_limit, daily_export_limit
            )
            VALUES (:id, :role_id, 100, NULL, 100)
            """
        ),
        [{"id": uuid.uuid4(), "role_id": role_id} for role_id in role_ids],
    )

    user_ids = [uuid.UUID(int=300_000 + index) for index in range(_ROLE_COUNT * _USERS_PER_ROLE)]
    await db_session.execute(
        text(
            """
            INSERT INTO users (
                id, username, display_name, role, role_id, auth_provider
            )
            VALUES (:id, :username, '', 'member', :role_id, 'oidc')
            """
        ),
        [
            {
                "id": user_id,
                "username": f"chunk12-status-{index}",
                "role_id": role_ids[index // _USERS_PER_ROLE],
            }
            for index, user_id in enumerate(user_ids)
        ],
    )
    return role_ids, user_ids


async def _seed_single_quota_status(db_session: AsyncSession) -> None:
    await db_session.execute(text("DELETE FROM role_quotas"))
    role_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await db_session.execute(
        text(
            """
            INSERT INTO roles (id, name, description, priority, permissions, is_builtin)
            VALUES (:id, :name, '', 62000, '[]'::jsonb, false)
            """
        ),
        {"id": role_id, "name": f"Chunk12 Single {role_id}"},
    )
    await db_session.execute(
        text(
            """
            INSERT INTO role_quotas (
                id, role_id, daily_query_limit,
                daily_execution_limit, daily_export_limit
            )
            VALUES (:id, :role_id, 100, NULL, NULL)
            """
        ),
        {"id": uuid.uuid4(), "role_id": role_id},
    )
    await db_session.execute(
        text(
            """
            INSERT INTO users (id, username, display_name, role, role_id, auth_provider)
            VALUES (:id, :username, '', 'member', :role_id, 'oidc')
            """
        ),
        {"id": user_id, "username": f"chunk12-single-{user_id}", "role_id": role_id},
    )


async def _admin_identity(db_session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    row = (
        await db_session.execute(
            text(
                """
                SELECT users.id AS user_id, roles.id AS role_id
                FROM users JOIN roles ON roles.id = users.role_id
                WHERE users.username = 'admin'
                """
            )
        )
    ).one()
    return row.user_id, row.role_id


@pytest.mark.asyncio
async def test_high_cardinality_status_uses_bounded_database_and_redis_batches(
    db_session: AsyncSession,
    async_engine_fixture: AsyncEngine,
    redis_client: Redis,
) -> None:
    admin_user_id, admin_role_id = await _admin_identity(db_session)
    role_ids, user_ids = await _seed_quota_status_dataset(db_session)
    date_suffix = datetime.now(UTC).strftime("%Y-%m-%d")
    await redis_client.mset(
        {f"quota:{user_ids[index * _USERS_PER_ROLE]}:queries:{date_suffix}": "3" for index in range(_ROLE_COUNT)}
    )
    recording_redis = RecordingQuotaRedis(redis_client)
    user_selects = 0

    def count_user_selects(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        nonlocal user_selects
        if statement.lstrip().upper().startswith("SELECT") and "FROM users" in statement:
            user_selects += 1

    event.listen(async_engine_fixture.sync_engine, "before_cursor_execute", count_user_selects)
    seen_role_ids: list[str] = []
    cursor: str | None = None
    try:
        async for client in _quota_status_client(
            db_session,
            recording_redis,
            admin_user_id,
            (admin_role_id, [str(Permission.ADMIN_QUOTAS_MANAGE)]),
        ):
            while True:
                response = await client.get(
                    "/api/v1/admin/quotas/status",
                    params={"limit": _ROLE_PAGE_LIMIT, **({"cursor": cursor} if cursor else {})},
                )
                assert response.status_code == 200
                page = response.json()
                assert len(page["status"]) <= _ROLE_PAGE_LIMIT
                assert page["total"] == _ROLE_COUNT
                for role_status in page["status"]:
                    assert role_status["dimensions"]["queries"]["used"] == 3
                    assert role_status["dimensions"]["executions"]["used"] == 0
                    assert role_status["dimensions"]["exports"]["used"] == 0
                seen_role_ids.extend(role_status["role_id"] for role_status in page["status"])
                cursor = page["next_cursor"]
                if cursor is None:
                    break
    finally:
        event.remove(async_engine_fixture.sync_engine, "before_cursor_execute", count_user_selects)

    # The final 500-user role page needs one empty keyset probe to prove completion.
    expected_user_batches = math.ceil((_ROLE_PAGE_LIMIT * _USERS_PER_ROLE) / _USER_BATCH_LIMIT) * 2 + 2
    assert seen_role_ids == [str(role_id) for role_id in role_ids]
    assert recording_redis.get_calls == 0
    assert recording_redis.mget_sizes
    assert max(recording_redis.mget_sizes) <= _REDIS_BATCH_LIMIT
    assert recording_redis.dimensions["executions"] == 0
    assert user_selects == expected_user_batches


@pytest.mark.asyncio
@pytest.mark.parametrize("counter_value", ["malformed", "-1", "01"])
async def test_noncanonical_counter_fails_whole_status_request_closed(
    db_session: AsyncSession,
    redis_client: Redis,
    counter_value: str,
) -> None:
    admin_user_id, admin_role_id = await _admin_identity(db_session)
    await _seed_single_quota_status(db_session)
    redis = StaticCounterRedis(redis_client, counter_value)

    async for client in _quota_status_client(
        db_session,
        redis,
        admin_user_id,
        (admin_role_id, [str(Permission.ADMIN_QUOTAS_MANAGE)]),
    ):
        response = await client.get("/api/v1/admin/quotas/status")

    assert response.status_code == 503
    assert response.json() == {"detail": {"error": "service_unavailable", "message_key": "error.service_unavailable"}}


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_cursor", ["not-a-cursor", "", "A" * 513])
async def test_invalid_quota_status_cursor_is_sanitized_without_counter_reads(
    db_session: AsyncSession,
    redis_client: Redis,
    invalid_cursor: str,
) -> None:
    admin_user_id, admin_role_id = await _admin_identity(db_session)
    redis = RecordingQuotaRedis(redis_client)

    async for client in _quota_status_client(
        db_session,
        redis,
        admin_user_id,
        (admin_role_id, [str(Permission.ADMIN_QUOTAS_MANAGE)]),
    ):
        response = await client.get(
            "/api/v1/admin/quotas/status",
            params={"cursor": invalid_cursor},
        )

    assert response.status_code == 400
    assert response.json() == {
        "detail": {"error": "invalid_cursor", "message_key": "error.invalidCursor"}
    }
    assert redis.mget_sizes == []


@pytest.mark.asyncio
async def test_redis_batch_failure_returns_no_partial_status(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    admin_user_id, admin_role_id = await _admin_identity(db_session)
    await _seed_single_quota_status(db_session)
    redis = FailingBatchRedis(redis_client)

    async for client in _quota_status_client(
        db_session,
        redis,
        admin_user_id,
        (admin_role_id, [str(Permission.ADMIN_QUOTAS_MANAGE)]),
    ):
        response = await client.get("/api/v1/admin/quotas/status")

    assert response.status_code == 503
    assert "status" not in response.json()
    assert response.json()["detail"] == {
        "error": "service_unavailable",
        "message_key": "error.service_unavailable",
    }


@pytest.mark.asyncio
async def test_unexpected_redis_batch_failure_is_sanitized(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    admin_user_id, admin_role_id = await _admin_identity(db_session)
    await _seed_single_quota_status(db_session)
    redis = UnexpectedFailingBatchRedis(redis_client)

    async for client in _quota_status_client(
        db_session,
        redis,
        admin_user_id,
        (admin_role_id, [str(Permission.ADMIN_QUOTAS_MANAGE)]),
    ):
        response = await client.get("/api/v1/admin/quotas/status")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "error": "service_unavailable",
            "message_key": "error.service_unavailable",
        }
    }


@pytest.mark.asyncio
async def test_cancelled_status_request_does_not_settle_with_partial_data(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    admin_user_id, admin_role_id = await _admin_identity(db_session)
    await _seed_single_quota_status(db_session)
    redis = BlockingBatchRedis(redis_client)

    async for client in _quota_status_client(
        db_session,
        redis,
        admin_user_id,
        (admin_role_id, [str(Permission.ADMIN_QUOTAS_MANAGE)]),
    ):
        request_task = asyncio.create_task(client.get("/api/v1/admin/quotas/status"))
        await redis.started.wait()
        request_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request_task


@pytest.mark.asyncio
async def test_permission_denial_reads_no_quota_counters(
    db_session: AsyncSession,
    redis_client: Redis,
) -> None:
    admin_user_id, admin_role_id = await _admin_identity(db_session)
    redis = RecordingQuotaRedis(redis_client)

    async for client in _quota_status_client(
        db_session,
        redis,
        admin_user_id,
        (admin_role_id, []),
    ):
        response = await client.get("/api/v1/admin/quotas/status")

    assert response.status_code == 403
    assert redis.get_calls == 0
    assert redis.mget_sizes == []
