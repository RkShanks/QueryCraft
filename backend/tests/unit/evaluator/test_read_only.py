"""T-090 — ReadOnlyRule unit tests. T-429 — dialect parameterization."""

import pytest

from app.db.models.enums import DatabaseType
from app.evaluator.rules.read_only import DIALECT_MAP, ReadOnlyRule
from app.evaluator.schema_context import SchemaContext


@pytest.fixture
def rule() -> ReadOnlyRule:
    return ReadOnlyRule()


@pytest.mark.asyncio
async def test_simple_select_passes(rule):
    passed, reason = await rule.evaluate("SELECT * FROM users", SchemaContext())
    assert passed is True
    assert reason is None


@pytest.mark.asyncio
async def test_insert_fails(rule):
    passed, reason = await rule.evaluate("INSERT INTO users VALUES (1)", SchemaContext())
    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_update_fails(rule):
    passed, reason = await rule.evaluate("UPDATE users SET x = 1", SchemaContext())
    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_delete_fails(rule):
    passed, reason = await rule.evaluate("DELETE FROM users", SchemaContext())
    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_drop_table_fails(rule):
    passed, reason = await rule.evaluate("DROP TABLE users", SchemaContext())
    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_create_table_fails(rule):
    passed, reason = await rule.evaluate("CREATE TABLE foo (id int)", SchemaContext())
    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_cte_select_passes(rule):
    passed, reason = await rule.evaluate("WITH x AS (SELECT 1) SELECT * FROM x", SchemaContext())
    assert passed is True
    assert reason is None


@pytest.mark.asyncio
async def test_cte_delete_fails(rule):
    passed, reason = await rule.evaluate("WITH x AS (DELETE FROM users RETURNING *) SELECT * FROM x", SchemaContext())
    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_alter_table_fails(rule):
    passed, reason = await rule.evaluate("ALTER TABLE users ADD COLUMN age int", SchemaContext())
    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_truncate_fails(rule):
    passed, reason = await rule.evaluate("TRUNCATE TABLE users", SchemaContext())
    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM users FOR UPDATE",
        "SELECT * FROM users FOR SHARE",
        "SELECT * FROM users FOR NO KEY UPDATE",
        "SELECT * FROM users FOR KEY SHARE",
    ],
)
async def test_select_for_lock_blocked(rule, sql):
    ok, msg = await rule.evaluate(sql, SchemaContext())
    assert not ok, f"{sql} should be blocked but passed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1 UNION SELECT 2",
        "SELECT 1 UNION ALL SELECT 2",
        "SELECT 1 INTERSECT SELECT 1",
        "SELECT 1 EXCEPT SELECT 2",
        # Recursive CTE with UNION
        "WITH RECURSIVE n(i) AS (SELECT 1 UNION SELECT i+1 FROM n WHERE i < 5) SELECT * FROM n",
    ],
)
async def test_set_operations_pass_read_only(rule, sql):
    ok, _ = await rule.evaluate(sql, SchemaContext())
    assert ok, f"{sql} is read-only and must pass"


@pytest.mark.asyncio
async def test_union_with_update_branch_blocked(rule):
    ok, msg = await rule.evaluate(
        "SELECT 1 UNION SELECT * FROM (UPDATE users SET name = 'x' RETURNING *) AS u",
        SchemaContext(),
    )
    assert not ok, "UNION containing UPDATE branch must be blocked"


class TestReadOnlyRuleDialectParameterization:
    """T-429: Verify dialect-aware parsing in ReadOnlyRule."""

    @pytest.mark.asyncio
    async def test_dialect_map_exists(self):
        """DIALECT_MAP maps all DatabaseType values to sqlglot dialect strings."""
        assert DIALECT_MAP[DatabaseType.POSTGRESQL] == "postgres"
        assert DIALECT_MAP[DatabaseType.MYSQL] == "mysql"
        assert DIALECT_MAP[DatabaseType.MSSQL] == "tsql"

    @pytest.mark.asyncio
    async def test_select_with_postgres_dialect(self):
        """SELECT passes when parsed with postgres dialect."""
        rule = ReadOnlyRule(dialect="postgres")
        passed, reason = await rule.evaluate("SELECT * FROM users", SchemaContext())
        assert passed is True

    @pytest.mark.asyncio
    async def test_select_with_mysql_dialect(self):
        """SELECT passes when parsed with mysql dialect."""
        rule = ReadOnlyRule(dialect="mysql")
        passed, reason = await rule.evaluate("SELECT * FROM users", SchemaContext())
        assert passed is True

    @pytest.mark.asyncio
    async def test_select_with_tsql_dialect(self):
        """SELECT passes when parsed with tsql dialect."""
        rule = ReadOnlyRule(dialect="tsql")
        passed, reason = await rule.evaluate("SELECT * FROM users", SchemaContext())
        assert passed is True

    @pytest.mark.asyncio
    async def test_insert_fails_across_all_dialects(self):
        """INSERT is rejected regardless of dialect."""
        for dialect in ["postgres", "mysql", "tsql"]:
            rule = ReadOnlyRule(dialect=dialect)
            passed, _ = await rule.evaluate("INSERT INTO users VALUES (1)", SchemaContext())
            assert passed is False, f"INSERT should fail with dialect={dialect}"

    @pytest.mark.asyncio
    async def test_default_dialect_is_postgres(self):
        """Default dialect is postgres for backward compatibility."""
        rule = ReadOnlyRule()
        assert rule.dialect == "postgres"

    @pytest.mark.asyncio
    async def test_from_database_type_classmethod(self):
        """from_database_type creates rule with correct dialect."""
        rule_pg = ReadOnlyRule.from_database_type(DatabaseType.POSTGRESQL)
        assert rule_pg.dialect == "postgres"

        rule_mysql = ReadOnlyRule.from_database_type(DatabaseType.MYSQL)
        assert rule_mysql.dialect == "mysql"

        rule_mssql = ReadOnlyRule.from_database_type(DatabaseType.MSSQL)
        assert rule_mssql.dialect == "tsql"
