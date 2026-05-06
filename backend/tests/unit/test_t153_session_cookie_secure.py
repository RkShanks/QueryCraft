"""T-153 regression test — Session cookie must have Secure flag from actual endpoint.

The existing test_session_cookie_flags.py calls set_cookie directly with
secure=True, which conceals the fact that the auth router passes secure=False.
This test hits the actual /auth/sign-in endpoint and inspects the response.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client_no_lifespan_db():
    """Provide an httpx client with the auth router but no external DB deps."""
    # Patch lifespan DB / Redis calls BEFORE importing create_app so the
    # mocked reference is captured by the lifespan decorator.
    with (
        patch("app.main._upsert_source_db_connection", new_callable=AsyncMock),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.main.dispose_engine", new_callable=AsyncMock),
    ):
        # Import inside patch context
        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
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
