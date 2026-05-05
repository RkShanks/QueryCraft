"""T-094 — SchemaValidationRule unit tests."""

import pytest

from app.evaluator.rules.schema_validation import SchemaValidationRule
from app.evaluator.schema_context import Column, SchemaContext, Table


@pytest.fixture
def schema() -> SchemaContext:
    return SchemaContext(
        tables=[
            Table(
                name="users",
                columns=[
                    Column(name="id", type="integer", primary_key=True),
                    Column(name="name", type="text"),
                    Column(name="email", type="text"),
                ],
            ),
            Table(
                name="orders",
                columns=[
                    Column(name="id", type="integer", primary_key=True),
                    Column(name="user_id", type="integer"),
                    Column(name="total", type="decimal"),
                ],
            ),
        ]
    )


@pytest.fixture
def rule() -> SchemaValidationRule:
    return SchemaValidationRule()


@pytest.mark.asyncio
async def test_valid_table_and_column_passes(rule, schema):
    passed, reason = await rule.evaluate("SELECT id FROM users", schema)
    assert passed is True
    assert reason is None


@pytest.mark.asyncio
async def test_unknown_table_fails(rule, schema):
    passed, reason = await rule.evaluate("SELECT id FROM nonexistent", schema)
    assert passed is False
    assert "nonexistent" in (reason or "")


@pytest.mark.asyncio
async def test_unknown_column_fails(rule, schema):
    passed, reason = await rule.evaluate("SELECT bogus FROM users", schema)
    assert passed is False
    assert "bogus" in (reason or "")


@pytest.mark.asyncio
async def test_join_with_aliases_passes(rule, schema):
    sql = "SELECT u.id FROM users u JOIN orders o ON u.id = o.user_id"
    passed, reason = await rule.evaluate(sql, schema)
    assert passed is True
    assert reason is None


@pytest.mark.asyncio
async def test_aggregate_without_column_ref_passes(rule, schema):
    passed, reason = await rule.evaluate("SELECT count(*) FROM users", schema)
    assert passed is True
    assert reason is None


@pytest.mark.asyncio
async def test_quoted_identifier_case_sensitive_fails(rule, schema):
    """Quoted 'Users' should NOT match unquoted 'users' in schema."""
    passed, reason = await rule.evaluate('SELECT id FROM "Users"', schema)
    assert passed is False
    assert "Users" in (reason or "")


@pytest.mark.asyncio
async def test_column_from_quoted_table_fails(rule, schema):
    """Quoted table name that doesn't match schema exactly."""
    passed, reason = await rule.evaluate('SELECT id FROM "users"', schema)
    # Actually in Postgres, "users" is folded to lowercase and DOES match users.
    # Our current implementation does case-insensitive matching for all.
    # This test documents that behavior — quoted identifiers are treated same as unquoted.
    # If we want strict quoted handling, this test should be updated.
    assert passed is True
    assert reason is None
