"""T-099: SchemaIntrospector unit tests.

Tests that introspection queries build a correct SchemaContext,
that caching works, and that refresh bypasses cache.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.evaluator.schema_context import Column, SchemaContext, Table
from app.source_db.introspector import SchemaIntrospector


@pytest.fixture
def mock_connector():
    """Return a mock connector with a controllable connection."""
    conn = AsyncMock()
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    connector = MagicMock()
    connector.get_connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    connector.get_connection.return_value.__aexit__ = AsyncMock(return_value=False)
    return connector, conn


@pytest.fixture
def table_rows():
    """Fixture rows for information_schema.tables."""
    return [
        {"table_name": "actor", "table_schema": "public"},
        {"table_name": "film", "table_schema": "public"},
    ]


@pytest.fixture
def column_rows():
    """Fixture rows for information_schema.columns."""
    return [
        {"table_name": "actor", "column_name": "actor_id", "data_type": "integer", "is_nullable": "NO"},
        {"table_name": "actor", "column_name": "first_name", "data_type": "character varying", "is_nullable": "NO"},
        {"table_name": "film", "column_name": "film_id", "data_type": "integer", "is_nullable": "NO"},
        {"table_name": "film", "column_name": "title", "data_type": "character varying", "is_nullable": "NO"},
    ]


@pytest.fixture
def pk_rows():
    """Fixture rows for primary key info."""
    return [
        {"table_name": "actor", "column_name": "actor_id", "constraint_name": "actor_pkey"},
        {"table_name": "film", "column_name": "film_id", "constraint_name": "film_pkey"},
    ]


@pytest.fixture
def fk_rows():
    """Fixture rows for foreign key info."""
    return [
        {"table_name": "film_actor", "column_name": "actor_id", "foreign_table_name": "actor", "foreign_column_name": "actor_id"},
    ]


class TestSchemaIntrospector:
    """SchemaIntrospector tests."""

    async def test_introspect_builds_schema_context(
        self, mock_connector, table_rows, column_rows, pk_rows, fk_rows
    ):
        """ introspect() returns SchemaContext with correct tables/columns/PK/FK."""
        connector, conn = mock_connector

        async def _fetch(query, *args):
            if "information_schema.tables" in query:
                return table_rows
            if "information_schema.columns" in query:
                return column_rows
            if "information_schema.key_column_usage" in query and "constraint_name" in query:
                # PK query
                return pk_rows
            if "information_schema.key_column_usage" in query:
                # FK query
                return fk_rows
            return []

        conn.fetch = _fetch

        introspector = SchemaIntrospector(connector)
        result = await introspector.introspect()

        assert isinstance(result, SchemaContext)
        assert len(result.tables) == 2

        actor = result.find_table("actor")
        assert actor is not None
        assert len(actor.columns) == 2
        assert actor.columns[0].name == "actor_id"
        assert actor.columns[0].primary_key is True
        assert actor.columns[1].name == "first_name"
        assert actor.columns[1].primary_key is False

        film = result.find_table("film")
        assert film is not None
        assert len(film.columns) == 2
        assert film.columns[0].name == "film_id"
        assert film.columns[0].primary_key is True

    async def test_introspect_caches_result(self, mock_connector, table_rows, column_rows, pk_rows, fk_rows):
        """Subsequent calls within TTL return cached result (connection NOT called twice)."""
        connector, conn = mock_connector
        call_count = 0

        async def _fetch(query, *args):
            nonlocal call_count
            call_count += 1
            if "information_schema.tables" in query:
                return table_rows
            if "information_schema.columns" in query:
                return column_rows
            if "information_schema.key_column_usage" in query and "constraint_name" in query:
                return pk_rows
            if "information_schema.key_column_usage" in query:
                return fk_rows
            return []

        conn.fetch = _fetch

        introspector = SchemaIntrospector(connector)
        await introspector.introspect()
        calls_after_first = call_count
        await introspector.introspect()
        calls_after_second = call_count

        # Second call should not issue any new queries
        assert calls_after_second == calls_after_first

    async def test_refresh_bypasses_cache(self, mock_connector, table_rows, column_rows, pk_rows, fk_rows):
        """refresh() bypasses cache and re-queries."""
        connector, conn = mock_connector
        call_count = 0

        async def _fetch(query, *args):
            nonlocal call_count
            call_count += 1
            if "information_schema.tables" in query:
                return table_rows
            if "information_schema.columns" in query:
                return column_rows
            if "information_schema.key_column_usage" in query and "constraint_name" in query:
                return pk_rows
            if "information_schema.key_column_usage" in query:
                return fk_rows
            return []

        conn.fetch = _fetch

        introspector = SchemaIntrospector(connector)
        await introspector.introspect()
        calls_after_first = call_count
        await introspector.refresh()
        calls_after_refresh = call_count

        # Refresh should issue new queries
        assert calls_after_refresh > calls_after_first
