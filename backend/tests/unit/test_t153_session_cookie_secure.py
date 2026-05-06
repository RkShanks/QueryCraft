"""T-153 regression test — Session cookie must have Secure flag from actual endpoint.

The existing test_session_cookie_flags.py calls set_cookie directly with
secure=True, which conceals the fact that the auth router passes secure=False.
This test hits the actual /auth/sign-in endpoint and inspects the response.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_sign_in_sets_secure_cookie(client):
    """The sign-in endpoint must set the Secure flag on the session_id cookie."""
    response = await client.post(
        "/api/v1/auth/sign-in",
        json={"username": "admin", "password": "admin123"},
        headers={"origin": "http://test"},
    )
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "Secure" in set_cookie, f"Cookie missing Secure flag: {set_cookie}"
