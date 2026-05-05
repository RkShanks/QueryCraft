"""T-092 — SingleStatementRule unit tests."""

import pytest

from app.evaluator.rules.single_statement import SingleStatementRule
from app.evaluator.schema_context import SchemaContext


@pytest.fixture
def rule() -> SingleStatementRule:
    return SingleStatementRule()


@pytest.mark.asyncio
async def test_single_select_passes(rule):
    passed, reason = await rule.evaluate("SELECT 1", SchemaContext())
    assert passed is True
    assert reason is None


@pytest.mark.asyncio
async def test_single_select_with_trailing_semicolon_passes(rule):
    passed, reason = await rule.evaluate("SELECT 1;", SchemaContext())
    assert passed is True
    assert reason is None


@pytest.mark.asyncio
async def test_two_statements_fails(rule):
    passed, reason = await rule.evaluate("SELECT 1; SELECT 2", SchemaContext())
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
