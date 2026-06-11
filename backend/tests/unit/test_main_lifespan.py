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
