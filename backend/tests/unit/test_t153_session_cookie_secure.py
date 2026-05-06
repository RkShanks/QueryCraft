"""T-153 regression test — Session cookie must have Secure flag from actual endpoint.

The existing test_session_cookie_flags.py calls set_cookie directly with
secure=True, which conceals the fact that the auth router passes secure=False.
This test hits the actual /auth/sign-in endpoint and inspects the response.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client_no_lifespan_db(monkeypatch):
    """Provide an httpx client with the auth router but no external DB deps."""
    # Mock lifespan DB / Redis calls so CI doesn't need real services
    monkeypatch.setattr("app.main._upsert_source_db_connection", AsyncMock())
    monkeypatch.setattr("app.main.init_redis", AsyncMock())
    monkeypatch.setattr("app.main.close_redis", AsyncMock())
    monkeypatch.setattr("app.main.dispose_engine", AsyncMock())

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_sign_in_sets_secure_cookie(client_no_lifespan_db):
    """The sign-in endpoint must set the Secure flag on the session_id cookie."""
    response = await client_no_lifespan_db.post(
        "/api/v1/auth/sign-in",
        json={"username": "admin", "password": "admin123"},
        headers={"origin": "http://test"},
    )
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "Secure" in set_cookie, f"Cookie missing Secure flag: {set_cookie}"
