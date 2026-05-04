"""Integration tests for Auth router (T-055).

Tests POST /auth/sign-in (200 + cookie, 401 wrong creds, 422 empty fields),
POST /auth/sign-out (204, 401 unauthenticated), GET /auth/me (200 profile, 401 expired).
"""

import pytest


class TestAuthRouter:
    """Auth router integration tests."""

    @pytest.mark.asyncio
    async def test_sign_in_success(self, app_client):
        """Valid credentials return 200 and set session cookie."""
        response = await app_client.post(
            "/api/v1/auth/sign-in",
            json={"username": "admin", "password": "admin123"},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 200
        assert "session_id" in response.cookies
        data = response.json()
        assert data["username"] == "admin"

    @pytest.mark.asyncio
    async def test_sign_in_wrong_creds(self, app_client):
        """Invalid credentials return 401."""
        response = await app_client.post(
            "/api/v1/auth/sign-in",
            json={"username": "admin", "password": "wrong"},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_sign_in_empty_fields(self, app_client):
        """Empty fields return 422."""
        response = await app_client.post(
            "/api/v1/auth/sign-in",
            json={"username": "", "password": ""},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_sign_out_authenticated(self, authenticated_client):
        """Sign-out returns 204."""
        response = await authenticated_client.post(
            "/api/v1/auth/sign-out",
            headers={"origin": "http://test"},
        )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_sign_out_unauthenticated(self, app_client):
        """Sign-out without session returns 401."""
        response = await app_client.post(
            "/api/v1/auth/sign-out",
            headers={"origin": "http://test"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_authenticated(self, authenticated_client):
        """GET /me returns profile for authenticated user."""
        response = await authenticated_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"

    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, app_client):
        """GET /me without session returns 401."""
        response = await app_client.get("/api/v1/auth/me")
        assert response.status_code == 401
