"""Regression coverage for IS-GAP-014 quota mutation recovery."""

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import text

from app.core.dependencies import get_redis
from app.core.exceptions import QuotaUnavailableError
from app.db.models.role_quota import RoleQuota
from app.services.quota_service import QuotaService


class _PublicationFaultRedis:
    def __init__(self, redis) -> None:
        self._redis = redis
        self.fail_publication = False

    def __getattr__(self, name: str):
        return getattr(self._redis, name)

    async def eval(self, script: str, numkeys: int, *args: str):
        script_arguments = args[numkeys:]
        if self.fail_publication and len(script_arguments) == 3:
            raise RedisConnectionError("private cache publication failure")
        return await self._redis.eval(script, numkeys, *args)


async def _admin_role_id(async_engine_fixture) -> uuid.UUID:
    async with async_engine_fixture.connect() as connection:
        return (
            await connection.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true"))
        ).scalar_one()


async def _quota_row(async_engine_fixture, role_id: uuid.UUID):
    async with async_engine_fixture.connect() as connection:
        return (
            await connection.execute(
                text("SELECT daily_query_limit, created_at, updated_at FROM role_quotas WHERE role_id = :role_id"),
                {"role_id": role_id},
            )
        ).one()


async def _quota_audit_count(async_engine_fixture, role_id: uuid.UUID) -> int:
    async with async_engine_fixture.connect() as connection:
        return int(
            await connection.scalar(
                text(
                    "SELECT COUNT(*) FROM audit_log_entries "
                    "WHERE action_type = 'quota.config.change' AND resource_id = :role_id"
                ),
                {"role_id": str(role_id)},
            )
            or 0
        )


async def _install_deferred_quota_failure(async_engine_fixture) -> None:
    async with async_engine_fixture.begin() as connection:
        await connection.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION chunk09_reject_quota_commit()
                RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    IF NEW.daily_query_limit = 7 THEN
                        RAISE EXCEPTION 'private deferred quota failure';
                    END IF;
                    RETURN NEW;
                END;
                $$
                """
            )
        )
        await connection.execute(
            text(
                """
                CREATE CONSTRAINT TRIGGER chunk09_quota_commit_failure
                AFTER INSERT OR UPDATE ON role_quotas
                DEFERRABLE INITIALLY DEFERRED
                FOR EACH ROW EXECUTE FUNCTION chunk09_reject_quota_commit()
                """
            )
        )


async def _drop_deferred_quota_failure(async_engine_fixture) -> None:
    async with async_engine_fixture.begin() as connection:
        await connection.execute(text("DROP TRIGGER IF EXISTS chunk09_quota_commit_failure ON role_quotas"))
        await connection.execute(text("DROP FUNCTION IF EXISTS chunk09_reject_quota_commit()"))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_put_publication_failure_applies_once_and_identical_retry_reconciles(
    authenticated_client,
    async_engine_fixture,
    redis_client,
):
    role_id = await _admin_role_id(async_engine_fixture)
    fault_redis = _PublicationFaultRedis(redis_client)

    async def quota_redis():
        yield fault_redis

    app = authenticated_client._transport.app
    app.dependency_overrides[get_redis] = quota_redis
    try:
        initial_response = await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 10},
        )
        assert initial_response.status_code == 200
        initial_row = await _quota_row(async_engine_fixture, role_id)
        initial_audits = await _quota_audit_count(async_engine_fixture, role_id)

        fault_redis.fail_publication = True
        failed_response = await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 4},
        )

        assert failed_response.status_code == 503
        assert failed_response.json() == {
            "error": "quota_sync_pending",
            "message_key": "error.quota_sync_pending",
            "mutation_applied": True,
        }
        applied_row = await _quota_row(async_engine_fixture, role_id)
        assert applied_row[0] == 4
        assert applied_row[1] == initial_row[1]
        assert applied_row[2] > initial_row[2]
        assert await _quota_audit_count(async_engine_fixture, role_id) == initial_audits + 1

        counter_keys_before_check = await redis_client.keys("quota:*")
        quota_repo = AsyncMock()
        quota_repo.get.return_value = RoleQuota(role_id=role_id, daily_query_limit=4)
        with pytest.raises(QuotaUnavailableError):
            await QuotaService(redis_client, quota_repo).check_and_increment(
                uuid.uuid4(),
                role_id,
                "queries",
            )
        assert await redis_client.keys("quota:*") == counter_keys_before_check

        pending_retry_response = await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 4},
        )
        assert pending_retry_response.status_code == 503
        assert pending_retry_response.json() == failed_response.json()
        assert await _quota_row(async_engine_fixture, role_id) == applied_row
        assert await _quota_audit_count(async_engine_fixture, role_id) == initial_audits + 1

        fault_redis.fail_publication = False
        retry_response = await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 4},
        )

        assert retry_response.status_code == 200
        retried_row = await _quota_row(async_engine_fixture, role_id)
        assert retried_row == applied_row
        assert await _quota_audit_count(async_engine_fixture, role_id) == initial_audits + 1
        assert (await QuotaService(redis_client, quota_repo).check_and_increment(uuid.uuid4(), role_id, "queries"))[
            1
        ] == 4
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_publication_failure_applies_once_and_pending_retry_reconciles(
    authenticated_client,
    async_engine_fixture,
    redis_client,
):
    role_id = await _admin_role_id(async_engine_fixture)
    fault_redis = _PublicationFaultRedis(redis_client)

    async def quota_redis():
        yield fault_redis

    app = authenticated_client._transport.app
    app.dependency_overrides[get_redis] = quota_redis
    try:
        initial_response = await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 3},
        )
        assert initial_response.status_code == 200
        initial_audits = await _quota_audit_count(async_engine_fixture, role_id)

        fault_redis.fail_publication = True
        failed_response = await authenticated_client.delete(f"/api/v1/admin/quotas/{role_id}")

        assert failed_response.status_code == 503
        assert failed_response.json() == {
            "error": "quota_sync_pending",
            "message_key": "error.quota_sync_pending",
            "mutation_applied": True,
        }
        async with async_engine_fixture.connect() as connection:
            remaining_rows = await connection.scalar(
                text("SELECT COUNT(*) FROM role_quotas WHERE role_id = :role_id"),
                {"role_id": role_id},
            )
        assert remaining_rows == 0
        assert await _quota_audit_count(async_engine_fixture, role_id) == initial_audits + 1

        counter_keys_before_check = await redis_client.keys("quota:*")
        quota_repo = AsyncMock()
        quota_repo.get.return_value = None
        with pytest.raises(QuotaUnavailableError):
            await QuotaService(redis_client, quota_repo).check_and_increment(
                uuid.uuid4(),
                role_id,
                "queries",
            )
        assert await redis_client.keys("quota:*") == counter_keys_before_check

        pending_retry_response = await authenticated_client.delete(f"/api/v1/admin/quotas/{role_id}")
        assert pending_retry_response.status_code == 503
        assert pending_retry_response.json() == failed_response.json()
        assert await _quota_audit_count(async_engine_fixture, role_id) == initial_audits + 1

        fault_redis.fail_publication = False
        retry_response = await authenticated_client.delete(f"/api/v1/admin/quotas/{role_id}")
        assert retry_response.status_code == 204
        assert await _quota_audit_count(async_engine_fixture, role_id) == initial_audits + 1
        assert (await QuotaService(redis_client, quota_repo).check_and_increment(uuid.uuid4(), role_id, "queries"))[
            1
        ] is None

        duplicate_response = await authenticated_client.delete(f"/api/v1/admin/quotas/{role_id}")
        assert duplicate_response.status_code == 404
        assert await _quota_audit_count(async_engine_fixture, role_id) == initial_audits + 1
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_commit_failure_rolls_back_audit_and_republishes_prior_config(
    authenticated_client,
    async_engine_fixture,
    redis_client,
):
    role_id = await _admin_role_id(async_engine_fixture)
    initial_response = await authenticated_client.put(
        f"/api/v1/admin/quotas/{role_id}",
        json={"daily_query_limit": 10},
    )
    assert initial_response.status_code == 200
    initial_row = await _quota_row(async_engine_fixture, role_id)
    initial_audits = await _quota_audit_count(async_engine_fixture, role_id)
    await _install_deferred_quota_failure(async_engine_fixture)

    app = authenticated_client._transport.app
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies=authenticated_client.cookies,
            headers={"origin": "http://test"},
        ) as client:
            response = await client.put(
                f"/api/v1/admin/quotas/{role_id}",
                json={"daily_query_limit": 7},
            )

        assert response.status_code == 500
        assert response.text == "Internal Server Error"
        assert await _quota_row(async_engine_fixture, role_id) == initial_row
        assert await _quota_audit_count(async_engine_fixture, role_id) == initial_audits

        quota_repo = AsyncMock()
        quota_repo.get.return_value = RoleQuota(role_id=role_id, daily_query_limit=10)
        assert (await QuotaService(redis_client, quota_repo).check_and_increment(uuid.uuid4(), role_id, "queries"))[
            1
        ] == 10
        assert quota_repo.get.await_count == 0
    finally:
        await _drop_deferred_quota_failure(async_engine_fixture)
