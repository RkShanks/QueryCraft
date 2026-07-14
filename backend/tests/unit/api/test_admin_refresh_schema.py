"""T-118: Admin refresh-schema router API tests.

Tests POST /admin/refresh-schema with admin key auth and cache invalidation.
This endpoint uses the legacy source-schema adapter and does not require the
shared platform-database truncation fixture used by integration tests.
"""

from unittest.mock import patch

import pytest

from app.api.v1 import admin as admin_module

pytestmark = pytest.mark.integration


class TestAdminRefreshSchema:
    """Verify the legacy admin refresh-schema endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_schema_success(self, app_client):
        """POST /admin/refresh-schema returns 200 with schema stats."""
        response = await app_client.post(
            "/api/v1/admin/refresh-schema",
            headers={"origin": "http://test", "X-Admin-Key": "test-admin-key-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "tables_count" in data
        assert "columns_count" in data
        assert "approximate_tokens" in data
        assert "refreshed_at" in data
        assert isinstance(data["tables_count"], int)
        assert isinstance(data["columns_count"], int)
        assert data["tables_count"] >= 0
        assert data["columns_count"] >= 0

    @pytest.mark.asyncio
    async def test_refresh_schema_unauthenticated(self, app_client):
        """Missing X-Admin-Key returns 401."""
        response = await app_client.post(
            "/api/v1/admin/refresh-schema",
            headers={"origin": "http://test"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["message_key"] == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_refresh_schema_forbidden_wrong_key(self, app_client):
        """Wrong X-Admin-Key returns 403."""
        response = await app_client.post(
            "/api/v1/admin/refresh-schema",
            headers={"origin": "http://test", "X-Admin-Key": "wrong-key"},
        )
        assert response.status_code == 403
        data = response.json()
        assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_refresh_schema_invalidates_cache(self, app_client):
        """Refresh invalidates the introspector cache."""
        introspector = admin_module._get_introspector()
        response = await app_client.post(
            "/api/v1/admin/refresh-schema",
            headers={"origin": "http://test", "X-Admin-Key": "test-admin-key-123"},
        )
        assert response.status_code == 200
        assert introspector._cache is not None
        first_cached_at = introspector._cached_at

        with patch.object(introspector, "_fetch_schema") as mock_fetch:
            mock_fetch.return_value = introspector._cache

            response = await app_client.post(
                "/api/v1/admin/refresh-schema",
                headers={"origin": "http://test", "X-Admin-Key": "test-admin-key-123"},
            )
            assert response.status_code == 200
            mock_fetch.assert_awaited_once()

        assert introspector._cached_at >= first_cached_at
