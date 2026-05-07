"""Shared fixtures for acceptance tests.

Provides client fixture and LLM mock for deterministic acceptance testing.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def acceptance_client(set_test_env) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx AsyncClient connected to the test FastAPI app."""
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def authenticated_acceptance_client(acceptance_client, ensure_db_connection) -> AsyncGenerator[AsyncClient, None]:
    """Provide a pre-authenticated httpx client (admin user signed in)."""
    response = await acceptance_client.post(
        "/api/v1/auth/sign-in",
        json={"username": "admin", "password": "admin123"},
        headers={"origin": "http://test"},
    )
    assert response.status_code == 200, f"Sign-in failed: {response.text}"
    yield acceptance_client


@pytest.fixture
def mock_llm_sql(monkeypatch):
    """Return a patch context manager that overrides LLM SQL generation.

    Usage inside an async test:
        with mock_llm_sql("SELECT 1"):
            response = await client.post(...)
    """

    def _make_context_manager(sql: str):
        return patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=AsyncMock(generate_sql=AsyncMock(return_value=sql)))

    return _make_context_manager
