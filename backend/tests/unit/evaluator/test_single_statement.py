"""T-092 — SingleStatementRule unit tests."""

import pytest

from app.evaluator.rules.single_statement import SingleStatementRule
from app.evaluator.schema_context import SchemaContext


@pytest.mark.asyncio
async def test_tsql_top_select_passes() -> None:
    rule = SingleStatementRule(dialect="tsql")

    passed, reason = await rule.evaluate("SELECT TOP 5 * FROM SalesLT.Customer", SchemaContext())

    assert passed is True
    assert reason is None


@pytest.fixture
def rule() -> SingleStatementRule:
    return SingleStatementRule(dialect="postgres")


@pytest.mark.asyncio
@pytest.mark.parametrize("dialect", ["postgres", "mysql"])
async def test_single_select_passes_for_postgres_and_mysql(dialect: str) -> None:
    passed, reason = await SingleStatementRule(dialect=dialect).evaluate("SELECT 1", SchemaContext())
    assert passed is True
    assert reason is None


@pytest.mark.asyncio
async def test_single_select_with_trailing_semicolon_passes(rule):
    passed, reason = await rule.evaluate("SELECT 1;", SchemaContext())
    assert passed is True
    assert reason is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dialect", "sql"),
    [
        ("postgres", "SELECT 1; SELECT 2"),
        ("mysql", "SELECT 1; SELECT 2"),
        ("tsql", "SELECT TOP 5 * FROM SalesLT.Customer; SELECT 2"),
    ],
)
async def test_multiple_statements_fail_for_every_supported_dialect(dialect: str, sql: str) -> None:
    passed, reason = await SingleStatementRule(dialect=dialect).evaluate(sql, SchemaContext())

    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_double_semicolon_fails(rule):
    passed, reason = await rule.evaluate("SELECT 1;;", SchemaContext())
    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_empty_string_fails(rule):
    passed, reason = await rule.evaluate("", SchemaContext())
    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_whitespace_only_fails(rule):
    passed, reason = await rule.evaluate("   ", SchemaContext())
    assert passed is False
    assert reason is not None
