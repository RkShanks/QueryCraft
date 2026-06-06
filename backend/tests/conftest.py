"""Shared pytest fixtures for backend tests (T-017).

Provides:
- async_engine: testcontainers PostgreSQL engine
- db_session: async session scoped per-test
- redis_client: testcontainers Redis client
- test_settings: overridden Settings for test isolation
- app_client: httpx AsyncClient with the FastAPI test app
- authenticated_client: pre-signed-in httpx client
- mock_llm: controllable SQL mock
"""

import asyncio
import base64
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from _pytest.fixtures import FixtureRequest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
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
    return base64.b64encode(b"test-encryption-key-32-bytes!" + b"123").decode()


@pytest.fixture(scope="session")
def test_env_vars(test_encryption_key: str) -> dict[str, str]:
    """Environment variables for test settings."""
    return {
        "DATABASE_URL": "postgresql+asyncpg://querycraft:querycraft_dev@localhost:5433/querycraft",
        "REDIS_URL": "redis://localhost:6379/1",
        "PLATFORM_ENCRYPTION_KEY": test_encryption_key,
        "ALLOWED_ORIGINS": "http://localhost:3000,http://test",
        "ADMIN_USERNAME": "admin",
        "ADMIN_DISPLAY_NAME": "Platform Administrator",
        "ADMIN_PASSWORD": "admin123",
        "ADMIN_API_KEY": "test-admin-key-123",
        "LLM_PROVIDER": "ollama",
        "LOG_LEVEL": "DEBUG",
        "SOURCE_DB_NAME": "source_analytics",
        "SOURCE_DB_HOST": "localhost",
        "SOURCE_DB_PORT": "5434",
        "SOURCE_DB_USER": "pagila_user",
        "SOURCE_DB_PASSWORD": "pagila_dev_pwd",
        "SOURCE_DB_SSL_MODE": "disable",
        "DB_CREDENTIAL_KEY": "d1OQc28ErbKH8nnhjNbchX5y_1EyXcfclkK1hPjPqFY=",
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
async def clean_audit_table(async_engine_fixture) -> AsyncGenerator[None, None]:
    """Truncate ``audit_log_entries`` before the test starts.

    The shared Postgres testcontainer persists audit rows across
    test sessions, so the manually-assigned ``sequence_number``
    keeps growing. Tests that assert on a known starting sequence
    (e.g. ``e1.sequence_number == 1``) or that insert tampered
    entries at fixed sequence numbers must request this fixture.

    Apply via ``@pytest.mark.usefixtures("clean_audit_table")`` on
    the test class — the fixture is intentionally NOT autouse on
    ``db_session`` because other tests rely on audit rows left
    behind by prior tests in the same session.
    """
    async with async_engine_fixture.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE audit_log_entries"))
    yield


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


@pytest_asyncio.fixture
async def ensure_db_connection(async_engine_fixture):
    """Ensure at least one source_database_connections row exists for tests."""
    from sqlalchemy import text

    async with async_engine_fixture.connect() as conn:
        result = await conn.execute(text("SELECT id FROM source_database_connections LIMIT 1"))
        row = result.fetchone()
        if row is None:
            await conn.execute(
                text(
                    """
                    INSERT INTO source_database_connections (
                        id, display_name, host, port, database_name, username,
                        encrypted_password, database_type, lifecycle_state, health_status,
                        schema_introspection_status
                    )
                    VALUES (
                        gen_random_uuid(), 'Test Source', 'localhost', 5434, 'source_analytics',
                        'source_readonly', 'enc', 'postgresql', 'active', 'healthy', 'success'
                    )
                    RETURNING id
                    """
                )
            )
            await conn.commit()


@pytest_asyncio.fixture
async def authenticated_client(app_client, ensure_db_connection) -> AsyncGenerator[AsyncClient, None]:
    """Provide a pre-authenticated httpx client (admin user signed in)."""
    # Sign in with test admin credentials
    response = await app_client.post(
        "/api/v1/auth/sign-in",
        json={"username": "admin", "password": "admin123"},
        headers={"origin": "http://test"},
    )
    assert response.status_code == 200, f"Sign-in failed: {response.text}"
    yield app_client


@pytest.fixture
def mock_llm():
    """Return a stub LLM provider that always generates a safe SELECT."""

    class StubLLM:
        async def generate_sql(
            self,
            question: str,
            schema_context: str,
            negative_examples: list[str] | None = None,
        ) -> str:
            return "SELECT 1 AS id"

    return StubLLM()


# ---------------------------------------------------------------------------
# Lifecycle invariant checkers (T-376, T-377)
#
# Marker API::
#   @pytest.mark.lifecycle("lock")          – LockInvariant via redis_client
#   @pytest.mark.lifecycle("feedback")      – FeedbackStateInvariant via db_session
#   @pytest.mark.lifecycle("session")       – SessionTouchInvariant via db_session
#   @pytest.mark.lifecycle("lock", "session") – multiple invariants
#
# Tests using mocks can override the per-checker fixture:
#   @pytest.fixture
#   def lifecycle_lock_checker(self, mock_redis):
#       return LockInvariant(mock_redis)
#
# If the dependency (redis_client / db_session) is unavailable the checker
# is silently skipped. Unexpected exceptions in snapshot/validate are NOT
# caught – they fail the test with a clear message.
# ---------------------------------------------------------------------------


@pytest.fixture
def lifecycle_lock_checker(request: FixtureRequest):
    """LockInvariant using the test's Redis client, or None if unavailable."""
    from tests.lifecycle.invariants import LockInvariant

    try:
        redis = request.getfixturevalue("redis_client")
    except pytest.skip.Exception:
        return None
    except pytest.FixtureLookupError:
        return None
    except RuntimeError:
        return None
    return LockInvariant(redis)


@pytest.fixture
def lifecycle_feedback_checker(request: FixtureRequest):
    """FeedbackStateInvariant using the test's DB session, or None if unavailable."""
    from tests.lifecycle.invariants import FeedbackStateInvariant

    try:
        db = request.getfixturevalue("db_session")
    except pytest.skip.Exception:
        return None
    except pytest.FixtureLookupError:
        return None
    except RuntimeError:
        return None
    return FeedbackStateInvariant(db)


@pytest.fixture
def lifecycle_session_checker(request: FixtureRequest):
    """SessionTouchInvariant using the test's DB session, or None if unavailable."""
    from tests.lifecycle.invariants import SessionTouchInvariant

    try:
        db = request.getfixturevalue("db_session")
    except pytest.skip.Exception:
        return None
    except pytest.FixtureLookupError:
        return None
    except RuntimeError:
        return None
    return SessionTouchInvariant(db)


_INVARIANT_FIXTURE_MAP: dict[str, str] = {
    "lock": "lifecycle_lock_checker",
    "feedback": "lifecycle_feedback_checker",
    "session": "lifecycle_session_checker",
}


@pytest.fixture
async def lifecycle_aware(request: FixtureRequest):
    """Snapshot/validate lifecycle invariants for ``@pytest.mark.lifecycle`` tests.

    The marker must have at least one positional argument naming the invariants
    to check. Usage without arguments is a configuration error.

    Snapshot is taken before the test body; validation runs after.
    Checker exceptions are NOT swallowed – they fail the test immediately.
    """
    marker = request.node.get_closest_marker("lifecycle")
    if marker is None:
        yield
        return

    names: tuple[str, ...] = marker.args if marker.args else ()
    if not names:
        pytest.fail(
            "Empty @pytest.mark.lifecycle marker. "
            "Supply invariant names, e.g. @pytest.mark.lifecycle('lock'). "
            "Valid names: lock, feedback, session"
        )

    checkers: list[Any] = []
    for name in names:
        if name not in _INVARIANT_FIXTURE_MAP:
            pytest.fail(f"Unknown lifecycle invariant: {name!r}. Valid: {set(_INVARIANT_FIXTURE_MAP)}")
        fixture_name = _INVARIANT_FIXTURE_MAP[name]
        try:
            checker = request.getfixturevalue(fixture_name)
        except pytest.skip.Exception:
            continue  # dependency unavailable, skip this checker
        if checker is not None:
            checkers.append(checker)

    before: dict[str, dict[str, Any]] = {}
    for checker in checkers:
        before[checker.name] = await checker.snapshot(None)

    yield

    issues: list[str] = []
    for checker in checkers:
        result = await checker.validate(before.get(checker.name, {}), None)
        issues.extend(result)

    if issues:
        pytest.fail("Lifecycle invariant violation(s):\n" + "\n".join(issues))


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Enforce @pytest.mark.lifecycle requires ``lifecycle_aware`` fixture.

    A test with ``@pytest.mark.lifecycle(...)`` that does not request
    ``lifecycle_aware`` in its fixture graph is a no-op and probably a bug.
    Fail clearly at collection time.

    Also auto-mark tests by directory for unambiguous gate taxonomy:
    tests/unit/ → unit, tests/integration/ → integration,
    tests/contract/ → contract, tests/acceptance/ → acceptance,
    tests/lifecycle/ → lifecycle.
    """
    for item in items:
        marker = item.get_closest_marker("lifecycle")
        if marker is None:
            continue
        fixturenames: set[str] = item.fixturenames
        if "lifecycle_aware" not in fixturenames:
            raise pytest.UsageError(
                f"{item.nodeid}: @pytest.mark.lifecycle({marker.args}) requires "
                "'lifecycle_aware' fixture. Add lifecycle_aware as a parameter "
                "or use @pytest.mark.usefixtures('lifecycle_aware')."
            )

    _DIR_MARKERS: dict[str, str] = {
        "/tests/unit/": "unit",
        "/tests/integration/": "integration",
        "/tests/contract/": "contract",
        "/tests/acceptance/": "acceptance",
        "/tests/lifecycle/": "lifecycle",
    }
    for item in items:
        path_str = str(item.path)
        for dir_fragment, marker_name in _DIR_MARKERS.items():
            if dir_fragment in path_str:
                if not item.get_closest_marker(marker_name):
                    item.add_marker(marker_name)
                break
