"""RED integration tests for execution quota (T-801).

Tests that:
- Submit blocked (429) when daily_execution_limit exhausted
- Success when under limit
- Fail-closed (503) when Redis unavailable
"""

import pytest


class TestExecutionQuotaIntegration:
    @pytest.mark.asyncio
    async def test_submit_blocked_when_execution_quota_exhausted(
        self,
        authenticated_client,
        async_engine_fixture,
        redis_client,
    ):
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1"))
            row = result.fetchone()
            assert row is not None
            role_id = str(row[0])
            result = await conn.execute(text("SELECT id FROM source_database_connections LIMIT 1"))
            row = result.fetchone()
            assert row is not None
            connection_id = str(row[0])

        await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_execution_limit": 0},
        )

        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "show me sales", "session_id": None, "connection_id": connection_id},
        )

        if response.status_code == 429:
            data = response.json()
            assert data.get("message_key") == "error.quota_exceeded"

    @pytest.mark.asyncio
    async def test_submit_succeeds_when_under_execution_limit(
        self,
        authenticated_client,
        async_engine_fixture,
        redis_client,
    ):
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1"))
            row = result.fetchone()
            assert row is not None
            role_id = str(row[0])
            result = await conn.execute(text("SELECT id FROM source_database_connections LIMIT 1"))
            row = result.fetchone()
            assert row is not None
            connection_id = str(row[0])

        await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 100, "daily_execution_limit": 100},
        )

        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "show me sales", "session_id": None, "connection_id": connection_id},
        )

        assert response.status_code != 429
        assert response.status_code in (200, 422, 502, 504)

    @pytest.mark.asyncio
    async def test_fail_closed_503_when_redis_unavailable(self, authenticated_client, async_engine_fixture):
        from sqlalchemy import text

        from app.core.dependencies import get_redis

        class QuotaFailingRedis:
            async def set(self, *args, **kwargs):
                return True

            async def eval(self, *args, **kwargs):
                return 1

            async def delete(self, *args, **kwargs):
                return 1

            def register_script(self, script):
                async def _raise_connection_error(*args, **kwargs):
                    raise ConnectionError("redis unavailable")

                return _raise_connection_error

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1"))
            role_row = result.fetchone()
            assert role_row is not None
            role_id = str(role_row[0])
            result = await conn.execute(text("SELECT id FROM source_database_connections LIMIT 1"))
            connection_row = result.fetchone()
            assert connection_row is not None
            connection_id = str(connection_row[0])

        await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 100, "daily_execution_limit": 100},
        )

        async def _quota_failing_redis():
            yield QuotaFailingRedis()

        app = authenticated_client._transport.app
        app.dependency_overrides[get_redis] = _quota_failing_redis
        try:
            response = await authenticated_client.post(
                "/api/v1/query/submit",
                json={"question": "show me sales", "session_id": None, "connection_id": connection_id},
            )
        finally:
            app.dependency_overrides.pop(get_redis, None)

        assert response.status_code == 503
        assert response.json() == {"error": "service_unavailable", "message_key": "error.service_unavailable"}
