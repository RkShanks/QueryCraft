"""Tests for dialect validation rule (T-430, FR-071, FR-092)."""

import pytest

from app.evaluator.rules.dialect_validation import DialectValidationRule
from app.evaluator.schema_context import SchemaContext


class TestDialectValidationRule:
    """Verify dialect validation: parse failure → reject with dialect hint."""

    @pytest.mark.asyncio
    async def test_valid_postgres_select_passes(self):
        """Valid PostgreSQL SELECT passes validation."""
        rule = DialectValidationRule(dialect="postgres")
        passed, reason = await rule.evaluate("SELECT id, name FROM users WHERE active = true", SchemaContext())
        assert passed is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_valid_mysql_select_passes(self):
        """Valid MySQL SELECT passes validation."""
        rule = DialectValidationRule(dialect="mysql")
        passed, reason = await rule.evaluate("SELECT id, name FROM users LIMIT 10", SchemaContext())
        assert passed is True

    @pytest.mark.asyncio
    async def test_valid_tsql_select_passes(self):
        """Valid T-SQL SELECT passes validation."""
        rule = DialectValidationRule(dialect="tsql")
        passed, reason = await rule.evaluate("SELECT TOP 10 id, name FROM users", SchemaContext())
        assert passed is True

    @pytest.mark.asyncio
    async def test_malformed_sql_rejected(self):
        """Malformed/unparseable SQL is rejected."""
        rule = DialectValidationRule(dialect="postgres")
        passed, reason = await rule.evaluate("SELECT FROM WHERE", SchemaContext())
        assert passed is False
        assert reason is not None
        assert "dialect" in reason.lower() or "parse" in reason.lower()

    @pytest.mark.asyncio
    async def test_empty_sql_rejected(self):
        """Empty SQL is rejected."""
        rule = DialectValidationRule(dialect="postgres")
        passed, reason = await rule.evaluate("", SchemaContext())
        assert passed is False

    @pytest.mark.asyncio
    async def test_whitespace_sql_rejected(self):
        """Whitespace-only SQL is rejected."""
        rule = DialectValidationRule(dialect="postgres")
        passed, reason = await rule.evaluate("   ", SchemaContext())
        assert passed is False

    @pytest.mark.asyncio
    async def test_from_database_type_classmethod(self):
        """from_database_type creates rule with correct dialect."""
        from app.db.models.enums import DatabaseType

        rule_pg = DialectValidationRule.from_database_type(DatabaseType.POSTGRESQL)
        assert rule_pg.dialect == "postgres"

        rule_mysql = DialectValidationRule.from_database_type(DatabaseType.MYSQL)
        assert rule_mysql.dialect == "mysql"

        rule_mssql = DialectValidationRule.from_database_type(DatabaseType.MSSQL)
        assert rule_mssql.dialect == "tsql"

    @pytest.mark.asyncio
    async def test_requires_explicit_dialect(self):
        """Dialect must be explicitly provided (no default)."""
        with pytest.raises(TypeError):
            DialectValidationRule()

    @pytest.mark.asyncio
    async def test_tsql_limit_rejected(self):
        """T-SQL must reject LIMIT syntax (FR-071, Wave 12 contract)."""
        rule = DialectValidationRule(dialect="tsql")
        passed, reason = await rule.evaluate("SELECT * FROM users LIMIT 10", SchemaContext())
        assert passed is False
        assert reason is not None
        assert "LIMIT" in reason
