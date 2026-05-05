"""Contract-test fixtures: authenticated session for Schemathesis.

T-124..T-126: Provides a valid session cookie for contract tests.
"""

import os

# Set test env vars BEFORE importing app modules (schemathesis loads the app
# at import time).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://querycraft:querycraft_dev@localhost:5433/querycraft")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("PLATFORM_ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcyExMjM=")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000,http://test")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_DISPLAY_NAME", "Platform Administrator")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key-123")
os.environ.setdefault("LLM_PROVIDER", "ollama")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("SOURCE_DB_NAME", "source_analytics")
os.environ.setdefault("SOURCE_DB_HOST", "localhost")
os.environ.setdefault("SOURCE_DB_PORT", "5434")
os.environ.setdefault("SOURCE_DB_USER", "pagila_user")
os.environ.setdefault("SOURCE_DB_PASSWORD", "pagila_dev_pwd")
os.environ.setdefault("SOURCE_DB_SSL_MODE", "disable")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture(scope="session")
def contract_app():
    """FastAPI app instance for contract tests."""
    return create_app()


@pytest_asyncio.fixture(scope="session")
async def contract_session_cookie(contract_app):
    """Return a valid session_id cookie for an admin user."""
    transport = ASGITransport(app=contract_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/sign-in",
            json={"username": "admin", "password": "admin123"},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 200
        session_id = response.cookies.get("session_id")
        assert session_id
        yield session_id
