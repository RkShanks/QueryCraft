"""Shared pytest fixtures for backend tests (T-017).

Provides:
- async_engine: testcontainers PostgreSQL engine
- db_session: async session scoped per-test
- redis_client: testcontainers Redis client
- test_settings: overridden Settings for test isolation
- app_client: httpx AsyncClient with the FastAPI test app
"""

import asyncio
import base64
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_encryption_key() -> str:
    """A valid base64-encoded 32-byte encryption key for tests."""
    return base64.b64encode(b"test-encryption-key-32-bytes!!" + b"123").decode()


@pytest.fixture(scope="session")
def test_env_vars(test_encryption_key: str) -> dict[str, str]:
    """Environment variables for test settings."""
    return {
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5433/test",
        "REDIS_URL": "redis://localhost:6379/1",
        "PLATFORM_ENCRYPTION_KEY": test_encryption_key,
        "ALLOWED_ORIGINS": "http://localhost:3000",
        "ADMIN_USERNAME": "testadmin",
        "ADMIN_DISPLAY_NAME": "Test Admin",
        "ADMIN_PASSWORD": "testpassword123",
        "LLM_PROVIDER": "ollama",
        "LOG_LEVEL": "DEBUG",
        "SOURCE_DB_NAME": "test_source",
        "SOURCE_DB_HOST": "localhost",
        "SOURCE_DB_PORT": "5434",
        "SOURCE_DB_USER": "test_readonly",
        "SOURCE_DB_PASSWORD": "test_source_pass",
    }


@pytest.fixture(autouse=True)
def set_test_env(test_env_vars: dict[str, str], monkeypatch):
    """Inject test environment variables for every test."""
    for key, value in test_env_vars.items():
        monkeypatch.setenv(key, value)

    # Clear the settings cache
    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest_asyncio.fixture
async def async_engine_fixture(test_env_vars):
    """Create a test async engine (uses real DB when available, else skips)."""
    url = test_env_vars["DATABASE_URL"]
    engine = create_async_engine(url, echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("PostgreSQL not available for integration test")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine_fixture) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional async session that rolls back after each test."""
    session_factory = async_sessionmaker(
        async_engine_fixture,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def redis_client(test_env_vars) -> AsyncGenerator[Redis, None]:
    """Provide a Redis client pointing to test DB (index 1)."""
    url = test_env_vars["REDIS_URL"]
    client = Redis.from_url(url, decode_responses=True)
    try:
        await client.ping()
    except Exception:
        pytest.skip("Redis not available for integration test")
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def app_client(set_test_env) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx AsyncClient connected to the test FastAPI app."""
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
