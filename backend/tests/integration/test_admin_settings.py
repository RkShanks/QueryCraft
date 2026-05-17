"""Integration tests for Admin Settings endpoints (T-320).

Tests GET /admin/settings and PATCH /admin/settings; verifies session-based
admin role auth. Refresh-schema still requires X-Admin-Key.
"""

import pytest


class TestAdminSettingsRouter:
    """Admin settings router integration tests."""

    @pytest.mark.asyncio
    async def test_get_settings_success(self, authenticated_client):
        """GET /admin/settings returns current cap for admin session."""
        response = await authenticated_client.get("/api/v1/admin/settings")
        assert response.status_code == 200
        data = response.json()
        assert "llm_context_cap" in data
        assert isinstance(data["llm_context_cap"], int)
        assert "max_regenerate_attempts" in data

    @pytest.mark.asyncio
    async def test_get_settings_unauthenticated(self, app_client):
        """GET /admin/settings without session returns 401."""
        response = await app_client.get("/api/v1/admin/settings")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_settings_non_admin_forbidden(self, app_client, async_engine_fixture):
        """Authenticated non-admin user gets 403 on /admin/settings."""
        from argon2 import PasswordHasher
        from sqlalchemy import text

        # Create a non-admin user
        async with async_engine_fixture.connect() as conn:
            ph = PasswordHasher()
            password_hash = ph.hash("userpass")
            await conn.execute(
                text(
                    """
                    INSERT INTO users (username, display_name, password_hash, role)
                    VALUES ('regular_user', 'Regular User', :pwd, 'user')
                    ON CONFLICT (username) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        password_hash = EXCLUDED.password_hash,
                        role = EXCLUDED.role,
                        updated_at = now()
                    """
                ),
                {"pwd": password_hash},
            )
            await conn.commit()

        # Sign in as non-admin
        resp = await app_client.post(
            "/api/v1/auth/sign-in",
            json={"username": "regular_user", "password": "userpass"},
            headers={"origin": "http://test"},
        )
        assert resp.status_code == 200, f"Sign-in failed: {resp.text}"

        response = await app_client.get("/api/v1/admin/settings")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_patch_settings_success(self, authenticated_client):
        """PATCH /admin/settings updates cap for admin session."""
        response = await authenticated_client.patch(
            "/api/v1/admin/settings",
            json={"llm_context_cap": 5, "max_regenerate_attempts": 4},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["llm_context_cap"] == 5
        assert data["max_regenerate_attempts"] == 4
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_patch_settings_validation_too_high(self, authenticated_client):
        """PATCH /admin/settings with cap > 10 returns 422."""
        response = await authenticated_client.patch(
            "/api/v1/admin/settings",
            json={"llm_context_cap": 15},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_patch_settings_validation_negative(self, authenticated_client):
        """PATCH /admin/settings with cap < 0 returns 422."""
        response = await authenticated_client.patch(
            "/api/v1/admin/settings",
            json={"llm_context_cap": -1},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_patch_settings_unauthenticated(self, app_client):
        """PATCH /admin/settings without session returns 401."""
        response = await app_client.patch(
            "/api/v1/admin/settings",
            json={"llm_context_cap": 3},
        )
        assert response.status_code == 401
