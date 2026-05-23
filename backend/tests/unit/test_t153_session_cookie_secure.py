"""T-153 regression test — Session cookie must have Secure flag from actual endpoint.

The existing test_session_cookie_flags.py calls set_cookie directly with
secure=True, which conceals the fact that the auth router passes secure=False.
This test hits the actual /auth/sign-in endpoint and inspects the response.

NOTE: This test requires the full FastAPI app lifespan (DB + Redis),
so it is marked as integration. Run locally with docker compose up,
or use pytest -m integration.
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sign_in_sets_secure_cookie(client):
    password = "admin123"
    response = await client.post(
        "/api/v1/auth/sign-in",
        json={"username": "admin", "password": password},
        headers={"origin": "http://test"},
    )
    if response.status_code == 401:
        password = "Avril142"
        response = await client.post(
            "/api/v1/auth/sign-in",
            json={"username": "admin", "password": password},
            headers={"origin": "http://test"},
        )
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "Secure" in set_cookie, f"Cookie missing Secure flag: {set_cookie}"
