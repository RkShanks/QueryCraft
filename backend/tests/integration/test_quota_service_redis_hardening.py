"""Real-Redis regressions for Phase 6A quota atomicity and reset behavior."""

import asyncio
import json
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from redis.asyncio import Redis

from app.core.exceptions import QuotaExceededError, QuotaUnavailableError
from app.db.models.role_quota import RoleQuota
from app.services.quota_service import QuotaService, _today_key_suffix


@pytest_asyncio.fixture
async def isolated_quota_redis() -> AsyncGenerator[Redis, None]:
    redis_url = os.environ.get("QUERYCRAFT_ISOLATED_REDIS_URL")
    if redis_url is None:
        pytest.skip("QUERYCRAFT_ISOLATED_REDIS_URL is required")
    redis = Redis.from_url(redis_url, decode_responses=True)
    await redis.ping()
    await redis.flushdb()
    yield redis
    await redis.flushdb()
    await redis.aclose()


@pytest.mark.asyncio
async def test_p6_fr_148_concurrent_requests_never_overshoot_limit(isolated_quota_redis):
    role_id = uuid.uuid4()
    user_id = uuid.uuid4()
    quota_repo = AsyncMock()
    quota_repo.get.return_value = RoleQuota(role_id=role_id, daily_query_limit=5)
    service = QuotaService(isolated_quota_redis, quota_repo)

    outcomes = await asyncio.gather(
        *(service.check_and_increment(user_id, role_id, "queries") for _ in range(25)),
        return_exceptions=True,
    )

    assert len([outcome for outcome in outcomes if isinstance(outcome, tuple)]) == 5
    assert len([outcome for outcome in outcomes if isinstance(outcome, QuotaExceededError)]) == 20

    await QuotaService.refresh_config_cache(
        isolated_quota_redis,
        role_id,
        RoleQuota(role_id=role_id, daily_query_limit=6),
    )
    assert (await service.check_and_increment(user_id, role_id, "queries"))[:2] == (6, 6)


@pytest.mark.asyncio
async def test_c6_l02_existing_counter_without_expiry_is_repaired(isolated_quota_redis):
    role_id = uuid.uuid4()
    user_id = uuid.uuid4()
    quota_repo = AsyncMock()
    quota_repo.get.return_value = RoleQuota(role_id=role_id, daily_query_limit=5)
    service = QuotaService(isolated_quota_redis, quota_repo)
    counter_key = f"quota:{user_id}:queries:{_today_key_suffix()}"
    await isolated_quota_redis.set(counter_key, "1")

    assert (await service.check_and_increment(user_id, role_id, "queries"))[:2] == (2, 5)
    assert 0 < await isolated_quota_redis.ttl(counter_key) <= 86400


@pytest.mark.asyncio
async def test_existing_valid_counter_expiry_is_not_extended(isolated_quota_redis):
    role_id = uuid.uuid4()
    user_id = uuid.uuid4()
    quota_repo = AsyncMock()
    quota_repo.get.return_value = RoleQuota(role_id=role_id, daily_query_limit=5)
    service = QuotaService(isolated_quota_redis, quota_repo)
    counter_key = f"quota:{user_id}:queries:{_today_key_suffix()}"
    await isolated_quota_redis.set(counter_key, "1", ex=120)
    ttl_before = await isolated_quota_redis.ttl(counter_key)

    await service.check_and_increment(user_id, role_id, "queries")

    ttl_after = await isolated_quota_redis.ttl(counter_key)
    assert 0 < ttl_after <= ttl_before <= 120


@pytest.mark.asyncio
async def test_p6_fr_154_concurrent_requests_roll_over_at_utc_midnight(isolated_quota_redis):
    role_id = uuid.uuid4()
    user_id = uuid.uuid4()
    quota_repo = AsyncMock()
    quota_repo.get.return_value = RoleQuota(role_id=role_id, daily_query_limit=4)
    service = QuotaService(isolated_quota_redis, quota_repo)
    before_midnight = datetime(2026, 7, 28, 23, 59, 59, 999999, tzinfo=UTC)
    after_midnight = datetime(2026, 7, 29, 0, 0, 0, tzinfo=UTC)

    with patch("app.services.quota_service.datetime") as quota_clock:
        quota_clock.now.return_value = before_midnight
        first_day = await asyncio.gather(*(service.check_and_increment(user_id, role_id, "queries") for _ in range(4)))
        quota_clock.now.return_value = after_midnight
        second_day = await asyncio.gather(*(service.check_and_increment(user_id, role_id, "queries") for _ in range(4)))

    assert sorted(outcome[0] for outcome in first_day) == [1, 2, 3, 4]
    assert sorted(outcome[0] for outcome in second_day) == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_t794_cache_expires_in_60_seconds_and_refreshes_repository(isolated_quota_redis):
    role_id = uuid.uuid4()
    user_id = uuid.uuid4()
    quota_repo = AsyncMock()
    quota_repo.get.return_value = RoleQuota(role_id=role_id, daily_query_limit=5)
    service = QuotaService(isolated_quota_redis, quota_repo)

    assert (await service.check_and_increment(user_id, role_id, "queries"))[1] == 5
    cache_key = f"quota_config:{role_id}"
    assert 0 < await isolated_quota_redis.ttl(cache_key) <= 60

    await isolated_quota_redis.expire(cache_key, 0)
    assert await isolated_quota_redis.get(cache_key) is None
    quota_repo.get.return_value = RoleQuota(role_id=role_id, daily_query_limit=8)

    assert (await service.check_and_increment(user_id, role_id, "queries"))[1] == 8
    assert quota_repo.get.await_count == 2


@pytest.mark.asyncio
async def test_cache_serialization_contains_only_quota_fields(isolated_quota_redis):
    role_id = uuid.uuid4()
    quota_repo = AsyncMock()
    quota_repo.get.return_value = RoleQuota(
        role_id=role_id,
        daily_query_limit=1,
        daily_execution_limit=2,
        daily_export_limit=3,
    )
    service = QuotaService(isolated_quota_redis, quota_repo)

    await service.check_and_increment(uuid.uuid4(), role_id, "queries")
    cache_payload = json.loads(await isolated_quota_redis.get(f"quota_config:{role_id}"))

    assert set(cache_payload) == {
        "daily_query_limit",
        "daily_execution_limit",
        "daily_export_limit",
        "revision",
    }


@pytest.mark.asyncio
async def test_malformed_cache_fails_closed_then_recovers_without_restart(isolated_quota_redis):
    role_id = uuid.uuid4()
    user_id = uuid.uuid4()
    quota_repo = AsyncMock()
    quota_repo.get.return_value = RoleQuota(role_id=role_id, daily_query_limit=2)
    service = QuotaService(isolated_quota_redis, quota_repo)
    cache_key = f"quota_config:{role_id}"
    await isolated_quota_redis.set(cache_key, "malformed", ex=60)

    with pytest.raises(QuotaUnavailableError):
        await service.check_and_increment(user_id, role_id, "queries")

    await isolated_quota_redis.delete(cache_key)
    assert (await service.check_and_increment(user_id, role_id, "queries"))[:2] == (1, 2)


@pytest.mark.asyncio
async def test_script_error_fails_closed_then_recovers_without_restart(isolated_quota_redis):
    role_id = uuid.uuid4()
    user_id = uuid.uuid4()
    quota_repo = AsyncMock()
    quota_repo.get.return_value = RoleQuota(role_id=role_id, daily_query_limit=2)
    service = QuotaService(isolated_quota_redis, quota_repo)
    counter_key = f"quota:{user_id}:queries:{_today_key_suffix()}"
    await isolated_quota_redis.set(counter_key, "malformed", ex=60)

    with pytest.raises(QuotaUnavailableError):
        await service.check_and_increment(user_id, role_id, "queries")

    await isolated_quota_redis.delete(counter_key)
    assert (await service.check_and_increment(user_id, role_id, "queries"))[:2] == (1, 2)


@pytest.mark.asyncio
async def test_quota_dimensions_remain_independent(isolated_quota_redis):
    role_id = uuid.uuid4()
    user_id = uuid.uuid4()
    quota_repo = AsyncMock()
    quota_repo.get.return_value = RoleQuota(
        role_id=role_id,
        daily_query_limit=1,
        daily_execution_limit=2,
        daily_export_limit=3,
    )
    service = QuotaService(isolated_quota_redis, quota_repo)

    assert (await service.check_and_increment(user_id, role_id, "queries"))[:2] == (1, 1)
    with pytest.raises(QuotaExceededError):
        await service.check_and_increment(user_id, role_id, "queries")
    assert (await service.check_and_increment(user_id, role_id, "executions"))[:2] == (1, 2)
    assert (await service.check_and_increment(user_id, role_id, "executions"))[:2] == (2, 2)
    assert (await service.check_and_increment(user_id, role_id, "exports"))[:2] == (1, 3)


@pytest.mark.asyncio
async def test_uncapped_quota_does_not_create_counter_state(isolated_quota_redis):
    role_id = uuid.uuid4()
    user_id = uuid.uuid4()
    quota_repo = AsyncMock()
    quota_repo.get.return_value = RoleQuota(role_id=role_id)
    service = QuotaService(isolated_quota_redis, quota_repo)

    assert (await service.check_and_increment(user_id, role_id, "queries"))[:2] == (0, None)
    cache_only_size = await isolated_quota_redis.dbsize()
    for _ in range(5):
        assert (await service.check_and_increment(user_id, role_id, "queries"))[:2] == (0, None)

    assert await isolated_quota_redis.dbsize() == cache_only_size == 1
