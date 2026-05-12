"""Integration tests for Admin Settings endpoints (T-320).

Tests GET /admin/settings and PATCH /admin/settings; verifies admin key auth
and llm_context_cap validation.
"""

import pytest


class TestAdminSettingsRouter:
    """Admin settings router integration tests."""

    @pytest.mark.asyncio
    async def test_get_settings_success(self, app_client):
        """GET /admin/settings returns current cap."""
        response = await app_client.get(
            "/api/v1/admin/settings",
            headers={"X-Admin-Key": "test-admin-key-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "llm_context_cap" in data
        assert isinstance(data["llm_context_cap"], int)

    @pytest.mark.asyncio
    async def test_get_settings_unauthorized(self, app_client):
        """GET /admin/settings without key returns 401."""
        response = await app_client.get("/api/v1/admin/settings")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_settings_forbidden(self, app_client):
        """GET /admin/settings with wrong key returns 403."""
        response = await app_client.get(
            "/api/v1/admin/settings",
            headers={"X-Admin-Key": "wrong-key"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_patch_settings_success(self, app_client):
        """PATCH /admin/settings updates cap."""
        response = await app_client.patch(
            "/api/v1/admin/settings",
            json={"llm_context_cap": 5},
            headers={"X-Admin-Key": "test-admin-key-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["llm_context_cap"] == 5
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_patch_settings_validation_too_high(self, app_client):
        """PATCH /admin/settings with cap > 10 returns 422."""
        response = await app_client.patch(
            "/api/v1/admin/settings",
            json={"llm_context_cap": 15},
            headers={"X-Admin-Key": "test-admin-key-123"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_patch_settings_validation_negative(self, app_client):
        """PATCH /admin/settings with cap < 0 returns 422."""
        response = await app_client.patch(
            "/api/v1/admin/settings",
            json={"llm_context_cap": -1},
            headers={"X-Admin-Key": "test-admin-key-123"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_patch_settings_unauthorized(self, app_client):
        """PATCH /admin/settings without key returns 401."""
        response = await app_client.patch(
            "/api/v1/admin/settings",
            json={"llm_context_cap": 3},
        )
        assert response.status_code == 401
