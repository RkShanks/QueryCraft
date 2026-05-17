"""Unit tests for lifespan startup helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.main import _sync_admin_user, _upsert_source_db_connection


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
    settings.PLATFORM_ENCRYPTION_KEY = "test-key"

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=result_mock)

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.main.get_async_session_factory", return_value=factory),
        patch("app.main.encrypt", return_value="encrypted"),
    ):
        await _upsert_source_db_connection(settings)

    calls = session.execute.call_args_list
    assert len(calls) >= 1
    # First call is SELECT
    assert "SELECT id" in str(calls[0][0][0])
    # Second call is INSERT
    assert "INSERT INTO database_connections" in str(calls[1][0][0])


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
    settings.PLATFORM_ENCRYPTION_KEY = "test-key"

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value="existing-id")
    session.execute = AsyncMock(return_value=result_mock)

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.main.get_async_session_factory", return_value=factory),
        patch("app.main.encrypt", return_value="encrypted_new"),
    ):
        await _upsert_source_db_connection(settings)

    calls = session.execute.call_args_list
    # Second call should be UPDATE
    assert "UPDATE database_connections" in str(calls[1][0][0])


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
    assert len(calls) == 1
    stmt = str(calls[0][0][0])
    assert "INSERT INTO users" in stmt
    assert "ON CONFLICT (username) DO UPDATE" in stmt
