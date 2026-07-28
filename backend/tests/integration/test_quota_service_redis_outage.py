"""Isolated Redis outage and recovery regression for P6-FR-153."""

import asyncio
import os
import socket
import uuid
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError
from testcontainers.redis import RedisContainer

from app.core.exceptions import QuotaUnavailableError
from app.db.models.role_quota import RoleQuota
from app.services.quota_service import QuotaService


async def _wait_until_redis_recovers(redis: Redis) -> None:
    for _attempt in range(100):
        try:
            if await redis.ping():
                return
        except (RedisError, OSError):
            await asyncio.sleep(0.1)
    raise AssertionError("isolated Redis did not recover")


def _available_local_port() -> int:
    with socket.socket() as port_probe:
        port_probe.bind(("", 0))
        return port_probe.getsockname()[1]


@pytest.mark.asyncio
async def test_p6_fr_153_outage_timeout_and_recovery_need_no_application_restart():
    if os.environ.get("QUERYCRAFT_RUN_DOCKER_OUTAGE_TESTS") != "1":
        pytest.skip("QUERYCRAFT_RUN_DOCKER_OUTAGE_TESTS=1 is required")

    redis_port = _available_local_port()
    container = RedisContainer("redis:7-alpine").with_bind_ports(6379, redis_port).start()
    wrapped_container = container.get_wrapped_container()
    redis = Redis(
        host=container.get_container_host_ip(),
        port=redis_port,
        decode_responses=True,
        socket_connect_timeout=0.2,
        socket_timeout=0.2,
    )
    role_id = uuid.uuid4()
    quota_repo = AsyncMock()
    quota_repo.get.return_value = RoleQuota(role_id=role_id, daily_query_limit=4)
    service = QuotaService(redis, quota_repo)
    user_id = uuid.uuid4()

    try:
        assert (await service.check_and_increment(user_id, role_id, "queries"))[:2] == (1, 4)

        wrapped_container.stop()
        with pytest.raises(QuotaUnavailableError):
            await service.check_and_increment(user_id, role_id, "queries")

        wrapped_container.start()
        await _wait_until_redis_recovers(redis)
        assert (await service.check_and_increment(user_id, role_id, "queries"))[:2] == (2, 4)

        wrapped_container.pause()
        try:
            with pytest.raises(QuotaUnavailableError):
                await service.check_and_increment(user_id, role_id, "queries")
        finally:
            wrapped_container.unpause()

        await _wait_until_redis_recovers(redis)
        assert (await service.check_and_increment(user_id, role_id, "queries"))[:2] == (3, 4)
    finally:
        await redis.aclose()
        container.stop()
