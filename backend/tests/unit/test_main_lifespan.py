"""Unit tests for application startup and shutdown."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import _sync_admin_user, _upsert_source_db_connection


_SHUTDOWN_CATEGORIES = (
    "source_connector",
    "llm_adapters",
    "session_middleware",
    "shared_redis",
    "database_engine",
)


def _lifespan_settings() -> MagicMock:
    settings = MagicMock()
    settings.LOG_LEVEL = "INFO"
    settings.DATABASE_URL = "postgresql+asyncpg://platform"
    settings.DB_CREDENTIAL_KEY = "test-key"
    return settings


def _closer(category: str, app, observed: list[tuple[str, bool]], fails: bool = False) -> AsyncMock:
    async def close() -> None:
        observed.append((category, app.state.readiness.accepts_traffic))
        if fails:
            raise RuntimeError("private shutdown detail")

    return AsyncMock(side_effect=close)


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_category", _SHUTDOWN_CATEGORIES)
async def test_lifespan_attempts_every_closer_after_one_ordinary_failure(failed_category):
    """IS-GAP-021: one failed resource cannot skip later independent cleanup."""
    from app.main import create_app, lifespan

    app = create_app()
    observed: list[tuple[str, bool]] = []
    closers = {
        category: _closer(category, app, observed, category == failed_category)
        for category in _SHUTDOWN_CATEGORIES
    }
    middleware = SimpleNamespace(aclose=closers["session_middleware"])
    shutdown_logger = MagicMock()

    with (
        patch("app.main.get_settings", return_value=_lifespan_settings()),
        patch("app.main.setup_logging"),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main._check_alembic_drift", new_callable=AsyncMock),
        patch("app.main.init_credential_provider"),
        patch("app.main._upsert_source_db_connection", new_callable=AsyncMock),
        patch("app.main._sync_admin_user", new_callable=AsyncMock),
        patch("app.api.v1.query.close_source_db_connector", closers["source_connector"]),
        patch("app.main.LLMProviderFactory.shutdown_all", closers["llm_adapters"]),
        patch("app.main.SessionMiddleware._instances", [middleware]),
        patch("app.main.close_redis", closers["shared_redis"]),
        patch("app.main.dispose_engine", closers["database_engine"]),
        patch("app.main.logger", shutdown_logger),
        pytest.raises(RuntimeError, match="^application shutdown failed$") as exc_info,
    ):
        async with lifespan(app):
            pass

    assert type(exc_info.value).__name__ == "ApplicationShutdownError"
    assert exc_info.value.failure_categories == (failed_category,)
    assert exc_info.value.failure_count == 1
    assert observed == [(category, False) for category in _SHUTDOWN_CATEGORIES]
    shutdown_logger.info.assert_not_called()
    shutdown_logger.error.assert_called_once_with(
        "application_shutdown_failed",
        failure_categories=(failed_category,),
        failure_count=1,
    )


@pytest.mark.asyncio
async def test_lifespan_aggregates_simultaneous_failures_and_all_middleware_instances():
    """Each middleware client is independent and failures retain only safe categories."""
    from app.main import create_app, lifespan

    app = create_app()
    observed: list[tuple[str, bool]] = []
    source_close = _closer("source_connector", app, observed, fails=True)
    llm_close = _closer("llm_adapters", app, observed)
    session_closers = [
        _closer("session_middleware", app, observed, fails=index != 1)
        for index in range(3)
    ]
    redis_close = _closer("shared_redis", app, observed)
    engine_close = _closer("database_engine", app, observed, fails=True)
    middleware_instances = [SimpleNamespace(aclose=close) for close in session_closers]
    failed_middleware_instances = middleware_instances[::2]
    shutdown_logger = MagicMock()

    with (
        patch("app.main.get_settings", return_value=_lifespan_settings()),
        patch("app.main.setup_logging"),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main._check_alembic_drift", new_callable=AsyncMock),
        patch("app.main.init_credential_provider"),
        patch("app.main._upsert_source_db_connection", new_callable=AsyncMock),
        patch("app.main._sync_admin_user", new_callable=AsyncMock),
        patch("app.api.v1.query.close_source_db_connector", source_close),
        patch("app.main.LLMProviderFactory.shutdown_all", llm_close),
        patch("app.main.SessionMiddleware._instances", middleware_instances),
        patch("app.main.close_redis", redis_close),
        patch("app.main.dispose_engine", engine_close),
        patch("app.main.logger", shutdown_logger),
        pytest.raises(RuntimeError, match="^application shutdown failed$") as exc_info,
    ):
        async with lifespan(app):
            pass

    expected_failures = (
        "source_connector",
        "session_middleware",
        "session_middleware",
        "database_engine",
    )
    assert exc_info.value.failure_categories == expected_failures
    assert exc_info.value.failure_count == 4
    assert observed == [
        ("source_connector", False),
        ("llm_adapters", False),
        ("session_middleware", False),
        ("session_middleware", False),
        ("session_middleware", False),
        ("shared_redis", False),
        ("database_engine", False),
    ]
    assert middleware_instances == failed_middleware_instances
    shutdown_logger.error.assert_called_once_with(
        "application_shutdown_failed",
        failure_categories=expected_failures,
        failure_count=4,
    )


@pytest.mark.asyncio
async def test_lifespan_does_not_suppress_cancellation():
    """Cancellation remains process control and stops ordinary cleanup aggregation."""
    from app.main import create_app, lifespan

    app = create_app()
    source_close = AsyncMock(side_effect=asyncio.CancelledError)
    llm_close = AsyncMock()

    with (
        patch("app.main.get_settings", return_value=_lifespan_settings()),
        patch("app.main.setup_logging"),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main._check_alembic_drift", new_callable=AsyncMock),
        patch("app.main.init_credential_provider"),
        patch("app.main._upsert_source_db_connection", new_callable=AsyncMock),
        patch("app.main._sync_admin_user", new_callable=AsyncMock),
        patch("app.api.v1.query.close_source_db_connector", source_close),
        patch("app.main.LLMProviderFactory.shutdown_all", llm_close),
        pytest.raises(asyncio.CancelledError),
    ):
        async with lifespan(app):
            pass

    source_close.assert_awaited_once_with()
    llm_close.assert_not_awaited()


@pytest.mark.asyncio
async def test_lifespan_closes_query_source_connector():
    """Application shutdown releases the module-level source pool."""
    from app.main import create_app, lifespan

    settings = MagicMock()
    settings.LOG_LEVEL = "INFO"
    settings.DATABASE_URL = "postgresql+asyncpg://platform"
    settings.DB_CREDENTIAL_KEY = "test-key"
    source_connector = MagicMock()
    source_connector.aclose = AsyncMock()
    app = create_app()

    with (
        patch("app.main.get_settings", return_value=settings),
        patch("app.main.setup_logging"),
        patch("app.main.init_redis", new_callable=AsyncMock),
        patch("app.main._check_alembic_drift", new_callable=AsyncMock),
        patch("app.main.init_credential_provider"),
        patch("app.main._upsert_source_db_connection", new_callable=AsyncMock),
        patch("app.main._sync_admin_user", new_callable=AsyncMock),
        patch("app.main.LLMProviderFactory.shutdown_all", new_callable=AsyncMock),
        patch("app.main.SessionMiddleware._instances", []),
        patch("app.main.close_redis", new_callable=AsyncMock),
        patch("app.main.dispose_engine", new_callable=AsyncMock),
        patch("app.api.v1.query._source_db_connector", source_connector),
    ):
        async with lifespan(app):
            pass

    source_connector.aclose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_startup_failure_never_reports_ready():
    from app.main import create_app, lifespan

    app = create_app()
    with (
        patch("app.main.init_redis", new=AsyncMock(side_effect=OSError("startup failed"))),
        pytest.raises(OSError, match="startup failed"),
    ):
        async with lifespan(app):
            pass

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health_response = await client.get("/health")
        ready_response = await client.get("/ready")

    assert health_response.status_code == 200
    assert health_response.json() == {"status": "live"}
    assert ready_response.status_code == 503
    assert ready_response.json() == {"status": "not_ready"}


@pytest.mark.asyncio
async def test_upsert_source_db_connection_inserts_when_missing():
    """_upsert_source_db_connection inserts row when none exists."""
    settings = MagicMock()
    settings.SOURCE_DB_NAME = "test_db"
    settings.SOURCE_DB_HOST = "localhost"
    settings.SOURCE_DB_PORT = 5434
    settings.SOURCE_DB_USER = "test_user"
    settings.SOURCE_DB_PASSWORD = "test_pass"
    settings.SOURCE_DB_SSL_MODE = "disable"
    settings.DB_CREDENTIAL_KEY = "test-fernet-key"

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=result_mock)

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_provider = MagicMock()
    mock_provider.encrypt.return_value = "fernet_encrypted"

    with (
        patch("app.main.get_async_session_factory", return_value=factory),
        patch("app.core.credential_provider.get_credential_provider", return_value=mock_provider),
    ):
        await _upsert_source_db_connection(settings)

    calls = session.execute.call_args_list
    assert len(calls) >= 1
    # First call is SELECT
    assert "SELECT id" in str(calls[0][0][0])
    # Second call is INSERT
    assert "INSERT INTO source_database_connections" in str(calls[1][0][0])
    # Verify Fernet encryption was used
    mock_provider.encrypt.assert_called_once_with("test_pass")


@pytest.mark.asyncio
async def test_upsert_source_db_connection_updates_when_exists():
    """_upsert_source_db_connection updates existing row with new env values."""
    settings = MagicMock()
    settings.SOURCE_DB_NAME = "test_db"
    settings.SOURCE_DB_HOST = "new_host"
    settings.SOURCE_DB_PORT = 5435
    settings.SOURCE_DB_USER = "new_user"
    settings.SOURCE_DB_PASSWORD = "new_pass"
    settings.SOURCE_DB_SSL_MODE = "require"
    settings.DB_CREDENTIAL_KEY = "test-fernet-key"

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value="existing-id")
    session.execute = AsyncMock(return_value=result_mock)

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_provider = MagicMock()
    mock_provider.encrypt.return_value = "fernet_encrypted_new"

    with (
        patch("app.main.get_async_session_factory", return_value=factory),
        patch("app.core.credential_provider.get_credential_provider", return_value=mock_provider),
    ):
        await _upsert_source_db_connection(settings)

    calls = session.execute.call_args_list
    # Second call should be UPDATE
    assert "UPDATE source_database_connections" in str(calls[1][0][0])
    # Verify Fernet encryption was used
    mock_provider.encrypt.assert_called_once_with("new_pass")


@pytest.mark.asyncio
async def test_sync_admin_user_inserts_or_updates():
    """_sync_admin_user upserts admin user from .env settings."""
    settings = MagicMock()
    settings.ADMIN_USERNAME = "admin"
    settings.ADMIN_DISPLAY_NAME = "Admin User"
    settings.ADMIN_PASSWORD = "secret"

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.execute = AsyncMock()

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("app.main.get_async_session_factory", return_value=factory):
        await _sync_admin_user(settings)

    calls = session.execute.call_args_list
    assert len(calls) == 2
    role_sync_stmt = str(calls[0][0][0])
    assert "UPDATE roles" in role_sync_stmt
    assert "admin.quotas.manage" in role_sync_stmt
    assert "admin.security.manage" in role_sync_stmt

    admin_upsert_stmt = str(calls[1][0][0])
    assert "INSERT INTO users" in admin_upsert_stmt
    assert "ON CONFLICT (username) DO UPDATE" in admin_upsert_stmt


@pytest.mark.asyncio
async def test_sync_admin_user_links_role_id():
    """_sync_admin_user retrieves the Admin role ID and associates it with the admin user."""
    settings = MagicMock()
    settings.ADMIN_USERNAME = "admin"
    settings.ADMIN_DISPLAY_NAME = "Admin User"
    settings.ADMIN_PASSWORD = "secret"

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    # Mock lookup of roles.id and insertion
    execute_mock = AsyncMock()
    session.execute = execute_mock

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("app.main.get_async_session_factory", return_value=factory):
        await _sync_admin_user(settings)

    # Verify that the query inserts role_id and updates it on conflict
    calls = execute_mock.call_args_list
    assert len(calls) >= 1

    # Let's inspect the query statement(s) executed
    stmt = str(calls[-1][0][0])
    assert "role_id" in stmt
    assert "role_id = EXCLUDED.role_id" in stmt or "role_id = roles.id" in stmt
