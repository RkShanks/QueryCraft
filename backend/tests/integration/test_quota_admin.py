"""RED integration tests for quota admin API (T-797).

Tests GET/PUT/DELETE /admin/quotas endpoints:
- 200 list for admin with admin.quotas.manage
- 403 for user without permission
- PUT creates/updates config
- DELETE removes config
- GET /{role_id} 404 for unconfigured role
- GET /status returns consumption status per role
- PUT emits quota.config.change audit event
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.db.models.role_quota import RoleQuota
from app.services.quota_service import QuotaService


class TestQuotaAdminList:
    @pytest.mark.asyncio
    async def test_list_quotas_returns_200_for_admin(self, authenticated_client):
        response = await authenticated_client.get("/api/v1/admin/quotas")
        assert response.status_code == 200
        data = response.json()
        assert "quotas" in data

    @pytest.mark.asyncio
    async def test_list_quotas_403_for_non_admin(self, app_client, async_engine_fixture):
        from argon2 import PasswordHasher
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            ph = PasswordHasher()
            password_hash = ph.hash("userpass")
            await conn.execute(
                text(
                    """
                    INSERT INTO roles (name, description, priority, permissions, is_builtin)
                    VALUES (
                        'QuotaNoPermsRole',
                        'Quota test role without quota permission',
                        9101,
                        '["query.submit"]'::jsonb,
                        false
                    )
                    ON CONFLICT (name) DO UPDATE SET
                        permissions = EXCLUDED.permissions,
                        updated_at = now()
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO users (username, display_name, password_hash, role, role_id, auth_provider)
                    SELECT 'quota_no_perms', 'No Perms', :pwd, 'admin', id, 'local'
                    FROM roles
                    WHERE name = 'QuotaNoPermsRole'
                    ON CONFLICT (username) DO UPDATE SET
                        password_hash = EXCLUDED.password_hash,
                        role = EXCLUDED.role,
                        role_id = EXCLUDED.role_id,
                        auth_provider = EXCLUDED.auth_provider,
                        updated_at = now()
                    """
                ),
                {"pwd": password_hash},
            )
            await conn.commit()

        resp = await app_client.post(
            "/api/v1/auth/sign-in",
            json={"username": "quota_no_perms", "password": "userpass"},
            headers={"origin": "http://test"},
        )
        assert resp.status_code == 200
        response = await app_client.get("/api/v1/admin/quotas")
        assert response.status_code == 403


class TestQuotaAdminPut:
    @pytest.mark.asyncio
    async def test_put_creates_quota_config(self, authenticated_client, async_engine_fixture):
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1"))
            row = result.fetchone()
            assert row is not None
            role_id = str(row[0])

        response = await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 10, "daily_execution_limit": 20},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["daily_query_limit"] == 10
        assert data["daily_execution_limit"] == 20

    @pytest.mark.asyncio
    async def test_put_updates_existing_quota(self, authenticated_client, async_engine_fixture):
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1"))
            row = result.fetchone()
            role_id = str(row[0])

        await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 5},
        )

        response = await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 15, "daily_execution_limit": 30},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["daily_query_limit"] == 15
        assert data["daily_execution_limit"] == 30

    @pytest.mark.asyncio
    async def test_put_rejects_invalid_limit_with_sanitized_validation_error(
        self, authenticated_client, async_engine_fixture
    ):
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1"))
            row = result.fetchone()
            role_id = str(row[0])

        response = await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": -1},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "validation"
        assert data["message_key"] == "error.validation.generic"
        assert "details" in data
        assert "daily_query_limit" in {detail["field"] for detail in data["details"]}
        assert "stack" not in data


class TestQuotaAdminDelete:
    @pytest.mark.asyncio
    async def test_delete_removes_quota(self, authenticated_client, async_engine_fixture):
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1"))
            row = result.fetchone()
            role_id = str(row[0])

        await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 10},
        )

        response = await authenticated_client.delete(f"/api/v1/admin/quotas/{role_id}")
        assert response.status_code == 204


class TestQuotaAdminGetByRole:
    @pytest.mark.asyncio
    async def test_get_by_role_id_404_unconfigured(self, authenticated_client, async_engine_fixture):
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(text("SELECT id FROM roles ORDER BY priority LIMIT 1"))
            row = result.fetchone()
            role_id = str(row[0]) if row else "00000000-0000-0000-0000-000000000000"

        response = await authenticated_client.get(f"/api/v1/admin/quotas/{role_id}")
        assert response.status_code == 404


class TestQuotaAdminStatus:
    @pytest.mark.asyncio
    async def test_status_returns_consumption(self, authenticated_client):
        response = await authenticated_client.get("/api/v1/admin/quotas/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestQuotaAdminAuditEvent:
    @pytest.mark.asyncio
    async def test_put_emits_quota_config_change_audit(self, authenticated_client, async_engine_fixture):
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1"))
            row = result.fetchone()
            role_id = str(row[0])

        await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 10},
        )

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT context FROM audit_log_entries "
                    "WHERE action_type = 'quota.config.change' "
                    "ORDER BY sequence_number DESC LIMIT 1"
                )
            )
            entry = result.fetchone()
            assert entry is not None
            context = entry[0] if isinstance(entry[0], dict) else __import__("json").loads(entry[0])
            assert "role_id" in context or "dims_changed" in context or "action" in context


class TestQuotaAdminCacheRefresh:
    @pytest.mark.asyncio
    async def test_upsert_and_delete_change_warm_cache_immediately(
        self,
        authenticated_client,
        async_engine_fixture,
        redis_client,
    ):
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            role_id = (
                await conn.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1"))
            ).scalar_one()

        await redis_client.delete(
            f"quota_config:{role_id}",
            f"quota_config_revision:{role_id}",
        )
        stale_quota = RoleQuota(role_id=role_id, daily_query_limit=10)
        quota_repo = AsyncMock()
        quota_repo.get.return_value = stale_quota
        service = QuotaService(redis=redis_client, quota_repo=quota_repo)
        user_id = uuid.uuid4()

        assert (await service.check_and_increment(user_id, role_id, "queries"))[1] == 10

        response = await authenticated_client.put(
            f"/api/v1/admin/quotas/{role_id}",
            json={"daily_query_limit": 2},
        )
        assert response.status_code == 200
        assert (await service.check_and_increment(user_id, role_id, "queries"))[1] == 2

        response = await authenticated_client.delete(f"/api/v1/admin/quotas/{role_id}")
        assert response.status_code == 204
        assert (await service.check_and_increment(user_id, role_id, "queries"))[1] is None
        assert quota_repo.get.await_count == 1

    @pytest.mark.asyncio
    async def test_cache_refresh_failure_returns_sanitized_503(
        self,
        authenticated_client,
        async_engine_fixture,
    ):
        from sqlalchemy import text

        from app.core.dependencies import get_redis

        class CacheFailingRedis:
            async def eval(self, *_args):
                raise ConnectionError("internal cache endpoint unavailable")

        async with async_engine_fixture.connect() as conn:
            role_id = (
                await conn.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1"))
            ).scalar_one()
            quota_count_before = await conn.scalar(
                text("SELECT COUNT(*) FROM role_quotas WHERE role_id = :role_id"),
                {"role_id": role_id},
            )
            audit_count_before = await conn.scalar(
                text(
                    "SELECT COUNT(*) FROM audit_log_entries "
                    "WHERE action_type = 'quota.config.change' AND resource_id = :role_id"
                ),
                {"role_id": str(role_id)},
            )

        async def failing_cache():
            yield CacheFailingRedis()

        app = authenticated_client._transport.app
        app.dependency_overrides[get_redis] = failing_cache
        try:
            response = await authenticated_client.put(
                f"/api/v1/admin/quotas/{role_id}",
                json={"daily_query_limit": 4},
            )
        finally:
            app.dependency_overrides.pop(get_redis, None)

        assert response.status_code == 503
        assert response.json() == {
            "error": "service_unavailable",
            "message_key": "error.service_unavailable",
        }
        async with async_engine_fixture.connect() as conn:
            assert (
                await conn.scalar(
                    text("SELECT COUNT(*) FROM role_quotas WHERE role_id = :role_id"),
                    {"role_id": role_id},
                )
                == quota_count_before
            )
            assert (
                await conn.scalar(
                    text(
                        "SELECT COUNT(*) FROM audit_log_entries "
                        "WHERE action_type = 'quota.config.change' AND resource_id = :role_id"
                    ),
                    {"role_id": str(role_id)},
                )
                == audit_count_before
            )
