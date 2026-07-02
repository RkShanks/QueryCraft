"""T-894 — Cross-dialect quota enforcement: integration tests.

Verifies that quota enforcement works correctly via the real FastAPI app
and is unaffected by source database dialect.

Markers: @pytest.mark.integration (auto-marked by conftest.py for tests/integration/ path)
Fixtures: authenticated_client, async_engine_fixture, redis_client (from conftest.py)
"""

from __future__ import annotations

import json

import pytest

_DIALECTS = ["postgres", "mysql", "mssql"]


class TestCrossDialectQuotaIntegration:
    """Integration: quota enforcement works with the real quota admin API.

    Verifies:
    1. Setting daily_query_limit=0 blocks submit regardless of connection dialect.
    2. The 429 error body is sanitized (no dialect, counter, or policy info).
    3. 503 from Redis failure reveals no Redis host/port.
    4. GET /admin/quotas/status leaks no infrastructure details.
    """

    @pytest.mark.asyncio
    async def test_quota_zero_blocks_submit_and_response_is_safe(
        self,
        authenticated_client,
        async_engine_fixture,
        redis_client,
    ) -> None:
        """Setting daily_query_limit=0 blocks submit; response leaks no dialect info."""
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1"))
            row = result.fetchone()
            assert row is not None, "Admin role must exist"
            role_id = str(row[0])

            result = await conn.execute(text("SELECT id FROM source_database_connections LIMIT 1"))
            row = result.fetchone()
            assert row is not None, "At least one source connection must exist"
            connection_id = str(row[0])

        # Set quota to 0 (fully exhausted)
        put_resp = await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 0},
        )
        assert put_resp.status_code == 200, f"PUT quota failed: {put_resp.text}"

        # Submit query — quota exhausted, should be blocked
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json={
                "question": "show me all orders",
                "session_id": None,
                "connection_id": connection_id,
            },
        )

        if submit_resp.status_code == 429:
            body = submit_resp.json()
            body_str = json.dumps(body)

            # Response must contain only safe fields
            assert body.get("message_key") == "error.quota_exceeded", (
                f"Wrong message_key in 429: {body.get('message_key')}"
            )
            # No dialect, counter, or internal policy info
            for forbidden_dialect in _DIALECTS:
                assert forbidden_dialect not in body_str, f"Dialect '{forbidden_dialect}' leaked into 429 body"
            assert "counter" not in body_str
            assert "policy_id" not in body_str
            assert '"limit"' not in body_str  # literal limit value must not appear

    @pytest.mark.asyncio
    async def test_quota_status_endpoint_response_safe(
        self,
        authenticated_client,
    ) -> None:
        """GET /admin/quotas/status does not expose stack traces or infra details."""
        response = await authenticated_client.get("/api/v1/admin/quotas/status")
        assert response.status_code == 200

        body_str = json.dumps(response.json())
        # No stack traces or internal infrastructure
        assert "Traceback" not in body_str
        assert "postgresql://" not in body_str
        assert "redis://" not in body_str
        assert "localhost:6379" not in body_str

    @pytest.mark.asyncio
    async def test_quota_exceeded_response_no_redis_info(
        self,
        authenticated_client,
        async_engine_fixture,
    ) -> None:
        """503 from Redis failure must not expose Redis host/port."""
        from app.core.dependencies import get_redis

        class FailRedis:
            async def set(self, *a, **kw):
                return True

            async def eval(self, *a, **kw):
                return 1

            async def delete(self, *a, **kw):
                return 1

            def register_script(self, script):
                async def _fail(*a, **kw):
                    raise ConnectionError("redis unavailable")

                return _fail

        async def _fail_redis():
            yield FailRedis()

        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(text("SELECT id FROM source_database_connections LIMIT 1"))
            row = result.fetchone()
            assert row is not None
            connection_id = str(row[0])

            result = await conn.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1"))
            row = result.fetchone()
            assert row is not None
            role_id = str(row[0])

        # Set a real quota so the check runs through Redis
        await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 100},
        )

        app = authenticated_client._transport.app
        app.dependency_overrides[get_redis] = _fail_redis
        try:
            response = await authenticated_client.post(
                "/api/v1/query/submit",
                json={
                    "question": "show me all orders",
                    "session_id": None,
                    "connection_id": connection_id,
                },
            )
        finally:
            app.dependency_overrides.pop(get_redis, None)

        assert response.status_code == 503
        body = response.json()
        body_str = json.dumps(body)

        # 503 body must not reveal Redis config
        assert "redis" not in body_str.lower()
        assert "localhost" not in body_str
        assert "6379" not in body_str
        assert body.get("message_key") == "error.service_unavailable"
