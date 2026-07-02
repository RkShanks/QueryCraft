"""T-894 — Cross-dialect quota enforcement: integration tests.

Verifies that quota enforcement works correctly via the real FastAPI app
and is unaffected by source database dialect.

Markers: @pytest.mark.integration (auto-marked by conftest.py for tests/integration/ path)
Fixtures: authenticated_client, async_engine_fixture, redis_client (from conftest.py)
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text

_DIALECTS = ["postgresql", "mysql", "mssql"]


class TestCrossDialectQuotaIntegration:
    """Integration: quota enforcement works with the real quota admin API.

    Verifies:
    1. Setting daily_query_limit=0 blocks submit for each database connection (PostgreSQL, MySQL, MSSQL).
    2. Setting daily_execution_limit=0 blocks submit before DB executor call.
    3. The 429 error body is sanitized (no dialect, counter, or policy info).
    4. 503 from Redis failure reveals no Redis host/port.
    5. GET /admin/quotas/status leaks no infrastructure details.
    """

    @pytest.fixture(autouse=True)
    def setup_stub_llm(self, monkeypatch) -> None:
        """Ensure all tests in this class use the StubLLM provider to avoid 502s."""
        from app.core.config import get_settings

        monkeypatch.setattr(get_settings(), "LLM_PROVIDER", "stub")

    async def _setup_dialect_connection(self, conn, dialect: str, role_id: str) -> str:
        """Insert a mock active connection for the given database dialect and map an Admin policy."""
        connection_id = str(uuid.uuid4())
        await conn.execute(
            text(
                """
                INSERT INTO source_database_connections (
                    id, display_name, host, port, database_name, username,
                    encrypted_password, database_type, lifecycle_state, health_status,
                    schema_introspection_status
                )
                VALUES (
                    :id, :name, 'localhost', 5432, 'testdb', 'user', 'pwd',
                    :db_type, 'active', 'healthy', 'success'
                )
                """
            ),
            {
                "id": connection_id,
                "name": f"{dialect.upper()} test conn",
                "db_type": dialect,
            },
        )
        # Map a policy allowing all tables so the role policy provider doesn't fail-closed with 422
        await conn.execute(
            text(
                """
                INSERT INTO role_connection_policies (
                    id, role_id, connection_id, allowed_tables, row_filters, column_masks
                )
                VALUES (
                    gen_random_uuid(), :role_id, :connection_id, '[{"table": "*"}]'::jsonb, '[]'::jsonb, '[]'::jsonb
                )
                """
            ),
            {
                "role_id": role_id,
                "connection_id": connection_id,
            },
        )
        return connection_id

    @pytest.mark.asyncio
    @pytest.mark.parametrize("dialect", _DIALECTS)
    async def test_quota_zero_blocks_submit_per_dialect(
        self,
        authenticated_client,
        async_engine_fixture,
        redis_client,
        dialect,
    ) -> None:
        """Setting daily_query_limit=0 blocks submit for each dialect connection."""
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            # 1. Clean existing connections for isolation
            await conn.execute(text("DELETE FROM source_database_connections"))

            # 2. Get Admin role ID
            result = await conn.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1"))
            row = result.fetchone()
            assert row is not None, "Admin role must exist"
            role_id = str(row[0])

            # 3. Setup connection for the parametrized dialect
            connection_id = await self._setup_dialect_connection(conn, dialect, role_id)
            await conn.commit()

        # 4. Set quota to 0 (fully exhausted)
        put_resp = await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 0},
        )
        assert put_resp.status_code == 200, f"PUT quota failed: {put_resp.text}"

        # 5. Submit query — quota exhausted, should be blocked
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json={
                "question": "show me all orders",
                "session_id": None,
                "connection_id": connection_id,
            },
        )

        assert submit_resp.status_code == 429, (
            f"Expected 429 for connection dialect '{dialect}', got {submit_resp.status_code}"
        )
        body = submit_resp.json()
        body_str = json.dumps(body)

        # Response must contain only safe fields
        assert body.get("message_key") == "error.quota_exceeded"
        # No dialect, counter, or internal policy info
        for forbidden_dialect in _DIALECTS:
            assert forbidden_dialect not in body_str, f"Dialect '{forbidden_dialect}' leaked into 429 body"
        assert "counter" not in body_str
        assert "policy_id" not in body_str
        assert '"limit"' not in body_str

    @pytest.mark.asyncio
    @pytest.mark.parametrize("dialect", _DIALECTS)
    async def test_execution_quota_blocks_before_db_execution_per_dialect(
        self,
        authenticated_client,
        async_engine_fixture,
        redis_client,
        dialect,
    ) -> None:
        """Verify execution quota blocks before source DB executor/adapter execution for each dialect connection."""
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            # 1. Clean connections
            await conn.execute(text("DELETE FROM source_database_connections"))

            # 2. Get Admin role
            result = await conn.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1"))
            row = result.fetchone()
            assert row is not None
            role_id = str(row[0])

            # 3. Setup connection for dialect
            connection_id = await self._setup_dialect_connection(conn, dialect, role_id)
            await conn.commit()

        # 4. Configure quota: high queries quota, but 0 execution quota
        await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 100, "daily_execution_limit": 0},
        )

        # 5. Submit query — should pass queries check, but fail before DB execution check
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json={
                "question": "show me sales",
                "session_id": None,
                "connection_id": connection_id,
            },
        )

        # The mock LLM in tests/conftest.py returns "SELECT 1 AS id" (valid read-only statement)
        # So execution quota check is reached and must fail with 429 BEFORE executing DB adapter
        assert submit_resp.status_code == 429, (
            f"Expected 429 blocked by execution quota for dialect '{dialect}', "
            f"got {submit_resp.status_code}: {submit_resp.text}"
        )
        data = submit_resp.json()
        assert data.get("message_key") == "error.quota_exceeded"
        # No leak of dialect, counter values, or limit details
        body_str = json.dumps(data)
        assert dialect not in body_str
        assert "counter" not in body_str
        assert "limit" not in body_str.replace("error.quota_exceeded", "")

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
