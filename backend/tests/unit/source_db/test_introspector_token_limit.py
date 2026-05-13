"""T-101: SchemaTokenLimitExceeded test.

Tests that introspection raises SchemaTokenLimitExceeded when estimated
token count exceeds MAX_SCHEMA_TOKENS.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import SchemaTokenLimitExceeded
from app.evaluator.schema_context import Column, SchemaContext, Table
from app.source_db.introspector import SchemaIntrospector


@pytest.fixture
def mock_connector():
    """Return a mock connector."""
    conn = AsyncMock()
    connector = MagicMock()
    connector.get_connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    connector.get_connection.return_value.__aexit__ = AsyncMock(return_value=False)
    return connector, conn


class TestSchemaTokenLimit:
    """Schema token limit escalation tests."""

    async def test_token_limit_exceeded_raises(self, mock_connector, monkeypatch):
        """When token count > MAX_SCHEMA_TOKENS, raise SchemaTokenLimitExceeded."""
        connector, conn = mock_connector

        # Build a huge schema that will exceed a low token limit
        huge_tables = [
            Table(
                name=f"table_{i}",
                schema_name="public",
                columns=[Column(name=f"col_{j}", type="character varying", nullable=False) for j in range(100)],
            )
            for i in range(50)
        ]
        SchemaContext(tables=huge_tables)

        async def _fetch(query, *args):
            if "information_schema.tables" in query:
                return [{"table_name": t.name, "table_schema": t.schema_name} for t in huge_tables]
            if "information_schema.columns" in query:
                rows = []
                for t in huge_tables:
                    for c in t.columns:
                        rows.append(
                            {
                                "table_name": t.name,
                                "column_name": c.name,
                                "data_type": c.type,
                                "is_nullable": "NO",
                            }
                        )
                return rows
            if "key_column_usage" in query:
                return []
            return []

        conn.fetch = _fetch

        introspector = SchemaIntrospector(connector)

        # Patch a very low token limit so the huge schema triggers it
        monkeypatch.setattr(introspector, "_ttl_seconds", 300)
        # We can't easily monkeypatch the global settings, so we patch the token
        # counting method to always return a high number when the schema is huge
        original_count = introspector._count_tokens
        introspector._count_tokens = lambda schema: 100_000

        with pytest.raises(SchemaTokenLimitExceeded) as exc_info:
            await introspector.introspect()

        assert exc_info.value.tokens == 100_000
        introspector._count_tokens = original_count

    async def test_under_limit_returns_schema(self, mock_connector):
        """When token count <= MAX_SCHEMA_TOKENS, return SchemaContext normally."""
        connector, conn = mock_connector

        [
            Table(
                name="actor",
                schema_name="public",
                columns=[
                    Column(name="actor_id", type="integer", nullable=False),
                    Column(name="first_name", type="character varying", nullable=False),
                ],
            )
        ]

        async def _fetch(query, *args):
            if "information_schema.tables" in query:
                return [{"table_name": "actor", "table_schema": "public"}]
            if "information_schema.columns" in query:
                return [
                    {
                        "table_name": "actor",
                        "column_name": "actor_id",
                        "data_type": "integer",
                        "is_nullable": "NO",
                    },
                    {
                        "table_name": "actor",
                        "column_name": "first_name",
                        "data_type": "character varying",
                        "is_nullable": "NO",
                    },
                ]
            if "key_column_usage" in query:
                return []
            return []

        conn.fetch = _fetch

        introspector = SchemaIntrospector(connector)
        result = await introspector.introspect()

        assert isinstance(result, SchemaContext)
        assert result.find_table("actor") is not None
