"""Contract-test fixtures: authenticated session for Schemathesis.

T-124..T-126: Provides a valid session cookie for contract tests.
"""

import os

import pytest_asyncio
import schemathesis
from httpx import ASGITransport, AsyncClient

# The canonical contract is OpenAPI 3.1. Schemathesis 3.x supports that
# version behind its explicit feature gate, which must be enabled before the
# contract modules call ``schemathesis.openapi.from_path`` during collection.
schemathesis.experimental.OPEN_API_3_1.enable()

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

from app.main import _shutdown_application, create_app  # noqa: E402


@pytest_asyncio.fixture
async def contract_request(set_test_env):
    # HTTPX ASGITransport leaves application resources on pytest's loop.
    # Close them there before entering Schemathesis's blocking portal.
    await _shutdown_application()

    def call(case, *, cookies=None):
        # Each call owns a complete lifespan. A shut-down app's middleware
        # must not be reused by another portal after it was unregistered.
        return case.call_asgi(app=create_app(), headers={"origin": "http://test"}, cookies=cookies)

    return call


@pytest_asyncio.fixture
async def contract_app(set_test_env):
    """FastAPI app instance for contract tests."""
    await _shutdown_application()
    try:
        yield create_app()
    finally:
        await _shutdown_application()


@pytest_asyncio.fixture
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

        # ASGITransport does not run application shutdown. Release clients
        # created on pytest's event loop before Schemathesis opens the same
        # app in its per-example blocking portal event loop.
        await _shutdown_application()
        yield session_id
