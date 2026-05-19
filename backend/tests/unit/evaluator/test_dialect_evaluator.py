"""Dialect evaluator tests (T-431, SC-027, SC-028).

Verifies dialect-specific read-only behavior across PostgreSQL, MySQL, and T-SQL.
"""

import pytest

from app.db.models.enums import DatabaseType
from app.evaluator.pipeline import Evaluator
from app.evaluator.rules.dialect_validation import DialectValidationRule
from app.evaluator.rules.read_only import ReadOnlyRule
from app.evaluator.schema_context import SchemaContext


def _make_evaluator(database_type: DatabaseType) -> Evaluator:
    """Build an evaluator configured for a specific database dialect."""
    return Evaluator(
        rules=[
            DialectValidationRule.from_database_type(database_type),
            ReadOnlyRule.from_database_type(database_type),
        ]
    )


class TestDialectSpecificSyntax:
    """Verify dialect-specific syntax acceptance/rejection."""

    @pytest.mark.asyncio
    async def test_pg_limit_accepted(self):
        """PostgreSQL accepts LIMIT syntax."""
        evaluator = _make_evaluator(DatabaseType.POSTGRESQL)
        result = await evaluator.evaluate("SELECT * FROM users LIMIT 10", SchemaContext())
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_mysql_limit_accepted(self):
        """MySQL accepts LIMIT syntax."""
        evaluator = _make_evaluator(DatabaseType.MYSQL)
        result = await evaluator.evaluate("SELECT * FROM users LIMIT 10", SchemaContext())
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_tsql_top_accepted(self):
        """T-SQL accepts TOP syntax."""
        evaluator = _make_evaluator(DatabaseType.MSSQL)
        result = await evaluator.evaluate("SELECT TOP 10 * FROM users", SchemaContext())
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_pg_select_with_limit_and_where(self):
        """PostgreSQL accepts complex SELECT with LIMIT and WHERE."""
        evaluator = _make_evaluator(DatabaseType.POSTGRESQL)
        result = await evaluator.evaluate(
            "SELECT id, name FROM users WHERE active = true ORDER BY name LIMIT 20",
            SchemaContext(),
        )
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_mysql_select_with_limit(self):
        """MySQL accepts SELECT with LIMIT."""
        evaluator = _make_evaluator(DatabaseType.MYSQL)
        sql = "SELECT id, name FROM orders WHERE status = 'pending' LIMIT 50"
        result = await evaluator.evaluate(sql, SchemaContext())
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_tsql_select_with_top(self):
        """T-SQL accepts SELECT with TOP."""
        evaluator = _make_evaluator(DatabaseType.MSSQL)
        sql = "SELECT TOP 50 id, name FROM orders WHERE status = 'pending'"
        result = await evaluator.evaluate(sql, SchemaContext())
        assert result.passed is True


class TestReadOnlyAcrossDialects:
    """Verify INSERT/UPDATE/DELETE rejected across all 3 dialects."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "database_type,sql",
        [
            (DatabaseType.POSTGRESQL, "INSERT INTO users VALUES (1, 'test')"),
            (DatabaseType.POSTGRESQL, "UPDATE users SET name = 'test'"),
            (DatabaseType.POSTGRESQL, "DELETE FROM users WHERE id = 1"),
            (DatabaseType.MYSQL, "INSERT INTO users VALUES (1, 'test')"),
            (DatabaseType.MYSQL, "UPDATE users SET name = 'test'"),
            (DatabaseType.MYSQL, "DELETE FROM users WHERE id = 1"),
            (DatabaseType.MSSQL, "INSERT INTO users VALUES (1, 'test')"),
            (DatabaseType.MSSQL, "UPDATE users SET name = 'test'"),
            (DatabaseType.MSSQL, "DELETE FROM users WHERE id = 1"),
        ],
    )
    async def test_write_operations_rejected(self, database_type, sql):
        """Write operations are rejected regardless of dialect."""
        evaluator = _make_evaluator(database_type)
        result = await evaluator.evaluate(sql, SchemaContext())
        assert result.passed is False, f"{sql} should be rejected for {database_type.value}"


class TestParseFailureWithDialectHint:
    """Verify parse failure produces dialect-specific rejection."""

    @pytest.mark.asyncio
    async def test_malformed_sql_rejected(self):
        """Malformed SQL is rejected with dialect_validation violation."""
        evaluator = _make_evaluator(DatabaseType.MSSQL)
        result = await evaluator.evaluate("SELECT FROM WHERE GROUP BY HAVING", SchemaContext())
        assert result.passed is False
        # Violation should be from dialect_validation rule
        assert any(v.rule_name == "dialect_validation" for v in result.violations)

    @pytest.mark.asyncio
    async def test_empty_sql_rejected(self):
        """Empty SQL is rejected."""
        evaluator = _make_evaluator(DatabaseType.POSTGRESQL)
        result = await evaluator.evaluate("", SchemaContext())
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_whitespace_only_rejected(self):
        """Whitespace-only SQL is rejected."""
        evaluator = _make_evaluator(DatabaseType.MYSQL)
        result = await evaluator.evaluate("   \n\t  ", SchemaContext())
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_dialect_violation_message_key(self):
        """Dialect validation failure uses correct message key."""
        evaluator = _make_evaluator(DatabaseType.POSTGRESQL)
        result = await evaluator.evaluate("SELECT FROM WHERE", SchemaContext())
        assert result.passed is False
        violation_keys = [v.message_key for v in result.violations]
        assert "evaluator.violation.dialectMismatch" in violation_keys
