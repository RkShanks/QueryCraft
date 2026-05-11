"""F-8: G-006 — admin endpoints require X-Admin-Key unconditionally.

Reproduction:
- POST /admin/refresh-schema with session cookie but no X-Admin-Key → 401/403.
- With valid X-Admin-Key → 200.
- Without either → 401.
"""

import pytest


class TestAdminAuth:
    """Admin router auth tests."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_refresh_schema_without_admin_key_returns_401(self, authenticated_client):
        """Authenticated user without X-Admin-Key cannot refresh schema."""
        resp = await authenticated_client.post("/api/v1/admin/refresh-schema")
        assert resp.status_code == 401

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_refresh_schema_with_valid_admin_key_returns_200(self, app_client):
        """Valid X-Admin-Key allows schema refresh."""
        resp = await app_client.post(
            "/api/v1/admin/refresh-schema",
            headers={"X-Admin-Key": "test-admin-key-123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "tables_count" in data

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_refresh_schema_without_any_auth_returns_401(self, app_client):
        """No session and no X-Admin-Key returns 401."""
        resp = await app_client.post("/api/v1/admin/refresh-schema")
        assert resp.status_code == 401
