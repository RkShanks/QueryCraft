"""Integration tests for Auth router (T-055).

Tests POST /auth/sign-in (200 + cookie, 401 wrong creds, 422 empty fields),
POST /auth/sign-out (204, 401 unauthenticated), GET /auth/me (200 profile, 401 expired).
"""

import pytest
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.dependencies import get_redis


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
    async def test_sign_in_session_store_failure_returns_sanitized_503(self, app_client):
        """Session creation fails closed when Redis is unavailable."""

        class FailingRedis:
            async def eval(self, *_args, **_kwargs):
                raise RedisConnectionError("private redis location")

            async def set(self, *_args, **_kwargs):
                raise RedisConnectionError("private redis location")

        async def failing_redis():
            yield FailingRedis()

        app = app_client._transport.app
        app.dependency_overrides[get_redis] = failing_redis
        try:
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/auth/sign-in",
                    json={"username": "admin", "password": "admin123"},
                    headers={"origin": "http://test"},
                )
        finally:
            app.dependency_overrides.pop(get_redis, None)

        assert response.status_code == 503
        assert response.json() == {
            "error": "service_unavailable",
            "message_key": "error.service_unavailable",
        }
        assert "session_id" not in response.cookies
        assert "private redis location" not in response.text

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
