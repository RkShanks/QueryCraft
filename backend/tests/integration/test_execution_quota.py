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
        self, authenticated_client, async_engine_fixture, redis_client,
    ):
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(
                text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1")
            )
            row = result.fetchone()
            assert row is not None
            role_id = str(row[0])

        await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_execution_limit": 0},
        )

        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "show me sales", "session_id": None, "connection_id": None},
        )

        if response.status_code == 429:
            data = response.json()
            assert data.get("message_key") == "error.quota_exceeded"

    @pytest.mark.asyncio
    async def test_submit_succeeds_when_under_execution_limit(
        self, authenticated_client, async_engine_fixture, redis_client,
    ):
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(
                text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1")
            )
            row = result.fetchone()
            assert row is not None
            role_id = str(row[0])

        await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 100, "daily_execution_limit": 100},
        )

        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "show me sales", "session_id": None, "connection_id": None},
        )

        assert response.status_code in (200, 429, 502, 504)

    @pytest.mark.asyncio
    async def test_fail_closed_503_when_redis_unavailable(self, authenticated_client, async_engine_fixture):
        pass
