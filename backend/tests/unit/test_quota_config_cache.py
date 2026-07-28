"""Regression coverage for the T-794 quota configuration cache."""

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest

from app.db.models.role_quota import RoleQuota
from app.services.quota_service import QuotaService


class _MemoryRedis:
    def __init__(self) -> None:
        self.entries: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.entries.get(key)

    async def set(self, key: str, payload: str, *, ex: int) -> bool:
        self.entries[key] = payload
        return True

    async def incr(self, key: str) -> int:
        revision = int(self.entries.get(key, "0")) + 1
        self.entries[key] = str(revision)
        return revision

    def register_script(self, _script: str):
        async def run_script(*, keys, args, client):
            return (1, 1, int(args[0]))

        return run_script


class _BlockingQuotaRepository:
    def __init__(self, quota: RoleQuota) -> None:
        self.quota = quota
        self.read_started = asyncio.Event()
        self.release_read = asyncio.Event()

    async def get(self, _role_id: uuid.UUID) -> RoleQuota:
        quota_snapshot = self.quota
        self.read_started.set()
        await self.release_read.wait()
        return quota_snapshot


@pytest.mark.asyncio
async def test_t794_cache_hit_avoids_repository_refresh():
    role_id = uuid.uuid4()
    user_id = uuid.uuid4()
    quota = RoleQuota(
        role_id=role_id,
        daily_query_limit=10,
        daily_execution_limit=20,
        daily_export_limit=30,
    )
    quota_repo = AsyncMock()
    quota_repo.get.return_value = quota
    service = QuotaService(redis=_MemoryRedis(), quota_repo=quota_repo)

    first = await service.check_and_increment(user_id, role_id, "queries")
    second = await service.check_and_increment(user_id, role_id, "queries")

    assert first[1] == second[1] == 10
    assert quota_repo.get.await_count == 1


@pytest.mark.asyncio
async def test_admin_change_refreshes_warm_cache_immediately():
    role_id = uuid.uuid4()
    user_id = uuid.uuid4()
    original_quota = RoleQuota(role_id=role_id, daily_query_limit=10)
    updated_quota = RoleQuota(role_id=role_id, daily_query_limit=2)
    quota_repo = AsyncMock()
    quota_repo.get.return_value = original_quota
    redis = _MemoryRedis()
    service = QuotaService(redis=redis, quota_repo=quota_repo)

    assert (await service.check_and_increment(user_id, role_id, "queries"))[1] == 10

    await QuotaService.refresh_config_cache(redis, role_id, updated_quota)
    assert (await service.check_and_increment(user_id, role_id, "queries"))[1] == 2

    await QuotaService.refresh_config_cache(redis, role_id, None)
    assert await service.check_and_increment(user_id, role_id, "queries") == (
        0,
        None,
        service._next_midnight(),
    )
    assert quota_repo.get.await_count == 1


@pytest.mark.asyncio
async def test_concurrent_admin_refresh_prevents_stale_cache_write():
    role_id = uuid.uuid4()
    user_id = uuid.uuid4()
    redis = _MemoryRedis()
    quota_repo = _BlockingQuotaRepository(RoleQuota(role_id=role_id, daily_query_limit=10))
    service = QuotaService(redis=redis, quota_repo=quota_repo)

    quota_check = asyncio.create_task(service.check_and_increment(user_id, role_id, "queries"))
    await quota_repo.read_started.wait()

    updated_quota = RoleQuota(role_id=role_id, daily_query_limit=2)
    await QuotaService.refresh_config_cache(redis, role_id, updated_quota)
    quota_repo.quota = updated_quota
    quota_repo.release_read.set()

    assert (await quota_check)[1] == 2
    assert (await service.check_and_increment(user_id, role_id, "queries"))[1] == 2
