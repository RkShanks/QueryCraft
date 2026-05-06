"""T-103: SourceDBConnector read-only test.

Tests that the connector opens a pool with decrypted credentials,
that the pool closes cleanly, and that read-only enforcement works
against the real pagila database.
"""

from unittest.mock import AsyncMock, patch

import asyncpg
import pytest

from app.core.config import get_settings
from app.source_db.connector import SourceDBConnector


class TestSourceDBConnectorUnit:
    """Unit tests for SourceDBConnector."""

    async def test_init_pool_decrypts_password(self):
        """init_pool decrypts SOURCE_DB_PASSWORD before passing to asyncpg."""
        from unittest.mock import AsyncMock

        mock_pool = AsyncMock()
        mock_create_pool = AsyncMock(return_value=mock_pool)

        with patch("app.source_db.connector.asyncpg.create_pool", mock_create_pool), \
             patch("app.source_db.connector.decrypt") as mock_decrypt:
            mock_decrypt.return_value = "decrypted_password"

            settings = get_settings()
            original_password = settings.SOURCE_DB_PASSWORD

            connector = SourceDBConnector()
            await connector.init_pool()

            # decrypt should be called with the raw password and encryption key
            mock_decrypt.assert_called_once_with(original_password, settings.PLATFORM_ENCRYPTION_KEY)
            # create_pool should receive the decrypted password
            call_kwargs = mock_create_pool.call_args.kwargs
            assert call_kwargs["password"] == "decrypted_password"

    async def test_init_pool_uses_source_db_settings(self):
        """init_pool creates pool with correct host/port/db/user from settings."""
        from unittest.mock import AsyncMock

        mock_pool = AsyncMock()
        mock_create_pool = AsyncMock(return_value=mock_pool)

        with patch("app.source_db.connector.asyncpg.create_pool", mock_create_pool), \
             patch("app.source_db.connector.decrypt") as mock_decrypt:
            mock_decrypt.return_value = "decrypted_password"

            settings = get_settings()

            connector = SourceDBConnector()
            await connector.init_pool()

            mock_create_pool.assert_called_once()
            call_kwargs = mock_create_pool.call_args.kwargs
            assert call_kwargs["host"] == settings.SOURCE_DB_HOST
            assert call_kwargs["port"] == settings.SOURCE_DB_PORT
            assert call_kwargs["database"] == settings.SOURCE_DB_NAME
            assert call_kwargs["user"] == settings.SOURCE_DB_USER
            assert call_kwargs["password"] == "decrypted_password"

    async def test_aclose_closes_pool(self):
        """aclose() closes the pool and clears the reference."""
        connector = SourceDBConnector()
        mock_pool = AsyncMock()
        connector._pool = mock_pool

        await connector.aclose()

        mock_pool.close.assert_awaited_once()
        assert connector._pool is None


@pytest.mark.integration
class TestSourceDBConnectorIntegration:
    """Integration tests against the real pagila source DB."""

    async def test_select_as_pagila_user(self, monkeypatch):
        """Open connection as pagila_user, SELECT count(*) FROM actor -> 200."""
        monkeypatch.setenv("SOURCE_DB_USER", "pagila_user")
        monkeypatch.setenv("SOURCE_DB_PASSWORD", "pagila_dev_pwd")
        from app.core.config import get_settings
        get_settings.cache_clear()

        connector = SourceDBConnector()
        await connector.init_pool()
        try:
            async with connector.get_connection() as conn:
                result = await conn.fetch("SELECT count(*) FROM actor")
                assert result[0]["count"] >= 200
        finally:
            await connector.aclose()

    async def test_insert_fails_for_pagila_user(self, monkeypatch):
        """Attempt INSERT into actor -> permission denied."""
        monkeypatch.setenv("SOURCE_DB_USER", "pagila_user")
        monkeypatch.setenv("SOURCE_DB_PASSWORD", "pagila_dev_pwd")
        from app.core.config import get_settings
        get_settings.cache_clear()

        connector = SourceDBConnector()
        await connector.init_pool()
        try:
            async with connector.get_connection() as conn:
                with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
                    await conn.fetch(
                        "INSERT INTO actor (first_name, last_name) VALUES ('Test', 'User')"
                    )
        finally:
            await connector.aclose()
