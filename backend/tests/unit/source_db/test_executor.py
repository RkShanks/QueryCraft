"""T-105: SourceDBExecutor timeout test.

Tests that execute(sql, timeout) returns (columns, rows) for successful SELECTs,
that timeouts raise SourceDBTimeout, and that various errors are wrapped correctly.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

from app.core.exceptions import (
    SourceDBConnectionFailed,
    SourceDBPermissionDenied,
    SourceDBTimeout,
)
from app.source_db.executor import SourceDBExecutor


class TestSourceDBExecutorUnit:
    """Unit tests for SourceDBExecutor."""

    async def test_execute_returns_columns_and_rows(self):
        """Successful SELECT returns (columns, rows)."""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {"actor_id": 1, "first_name": "Penelope"},
            {"actor_id": 2, "first_name": "Nick"},
        ]

        mock_connector = MagicMock()
        mock_connector.get_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_connector.get_connection.return_value.__aexit__ = AsyncMock(return_value=False)

        executor = SourceDBExecutor(mock_connector)
        columns, rows = await executor.execute("SELECT actor_id, first_name FROM actor LIMIT 2", timeout=30.0)

        assert columns == ["actor_id", "first_name"]
        assert rows == [(1, "Penelope"), (2, "Nick")]

    async def test_execute_sets_statement_timeout(self):
        """Execute sets SET LOCAL statement_timeout before query."""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = []

        mock_connector = MagicMock()
        mock_connector.get_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_connector.get_connection.return_value.__aexit__ = AsyncMock(return_value=False)

        executor = SourceDBExecutor(mock_connector)
        await executor.execute("SELECT 1", timeout=5.0)

        # Should set statement_timeout
        calls = [c.args[0] for c in mock_conn.execute.call_args_list]
        assert any("statement_timeout" in str(c) for c in calls)

    async def test_timeout_less_than_query_duration_raises(self):
        """timeout < query duration -> raises SourceDBTimeout."""
        mock_conn = AsyncMock()

        async def slow_fetch(*args, **kwargs):
            import asyncio
            await asyncio.sleep(0.5)
            return []

        mock_conn.fetch = slow_fetch

        mock_connector = MagicMock()
        mock_connector.get_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_connector.get_connection.return_value.__aexit__ = AsyncMock(return_value=False)

        executor = SourceDBExecutor(mock_connector)
        with pytest.raises(SourceDBTimeout):
            await executor.execute("SELECT pg_sleep(2)", timeout=0.1)

    async def test_timeout_greater_than_query_duration_ok(self):
        """timeout > query duration -> completes normally."""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [{"count": 1}]

        mock_connector = MagicMock()
        mock_connector.get_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_connector.get_connection.return_value.__aexit__ = AsyncMock(return_value=False)

        executor = SourceDBExecutor(mock_connector)
        columns, rows = await executor.execute("SELECT count(*) FROM actor", timeout=30.0)
        assert rows == [(1,)]

    async def test_query_canceled_raises_source_db_timeout(self):
        """asyncpg QueryCanceledError -> SourceDBTimeout."""
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = None
        mock_conn.fetch.side_effect = asyncpg.exceptions.QueryCanceledError("query canceled")

        mock_connector = MagicMock()
        mock_connector.get_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_connector.get_connection.return_value.__aexit__ = AsyncMock(return_value=False)

        executor = SourceDBExecutor(mock_connector)
        with pytest.raises(SourceDBTimeout):
            await executor.execute("SELECT 1", timeout=1.0)

    async def test_insufficient_privilege_raises(self):
        """asyncpg InsufficientPrivilegeError -> SourceDBPermissionDenied."""
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = None
        mock_conn.fetch.side_effect = asyncpg.exceptions.InsufficientPrivilegeError("permission denied")

        mock_connector = MagicMock()
        mock_connector.get_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_connector.get_connection.return_value.__aexit__ = AsyncMock(return_value=False)

        executor = SourceDBExecutor(mock_connector)
        with pytest.raises(SourceDBPermissionDenied):
            await executor.execute("INSERT INTO actor VALUES (1)", timeout=1.0)

    async def test_connection_error_raises(self):
        """Connection errors -> SourceDBConnectionFailed."""
        mock_connector = MagicMock()
        mock_connector.get_connection.side_effect = asyncpg.exceptions.ConnectionDoesNotExistError()

        executor = SourceDBExecutor(mock_connector)
        with pytest.raises(SourceDBConnectionFailed):
            await executor.execute("SELECT 1", timeout=1.0)


@pytest.mark.integration
class TestSourceDBExecutorIntegration:
    """Integration tests against real pagila DB."""

    async def test_select_against_pagila(self):
        """Execute SELECT against pagila returns columns and rows."""
        from app.source_db.connector import SourceDBConnector
        connector = SourceDBConnector()
        await connector.init_pool()
        try:
            executor = SourceDBExecutor(connector)
            columns, rows = await executor.execute(
                "SELECT first_name FROM actor LIMIT 5",
                timeout=30.0,
            )
            assert columns == ["first_name"]
            assert len(rows) == 5
        finally:
            await connector.aclose()
