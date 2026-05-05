"""T-090 — ReadOnlyRule unit tests."""

import pytest

from app.evaluator.rules.read_only import ReadOnlyRule
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
    passed, reason = await rule.evaluate(
        "WITH x AS (SELECT 1) SELECT * FROM x", SchemaContext()
    )
    assert passed is True
    assert reason is None


@pytest.mark.asyncio
async def test_cte_delete_fails(rule):
    passed, reason = await rule.evaluate(
        "WITH x AS (DELETE FROM users RETURNING *) SELECT * FROM x", SchemaContext()
    )
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
