"""T-096 — UnsafePatternRule unit tests."""

import pytest

from app.evaluator.rules.unsafe_pattern import UnsafePatternRule
from app.evaluator.schema_context import SchemaContext


@pytest.fixture
def rule() -> UnsafePatternRule:
    return UnsafePatternRule()


# --- Reject cases ---

@pytest.mark.asyncio
async def test_pg_sleep_rejected(rule):
    passed, reason = await rule.evaluate("SELECT pg_sleep(10)", SchemaContext())
    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_copy_to_rejected(rule):
    passed, reason = await rule.evaluate("COPY users TO '/tmp/x'", SchemaContext())
    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_lo_export_rejected(rule):
    passed, reason = await rule.evaluate("SELECT lo_export(1, '/tmp/x')", SchemaContext())
    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_pg_read_file_rejected(rule):
    passed, reason = await rule.evaluate("SELECT pg_read_file('/etc/passwd')", SchemaContext())
    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_pg_authid_rejected(rule):
    passed, reason = await rule.evaluate("SELECT * FROM pg_authid", SchemaContext())
    assert passed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_set_statement_timeout_rejected(rule):
    passed, reason = await rule.evaluate("SET statement_timeout = 0", SchemaContext())
    assert passed is False
    assert reason is not None


# --- Allow cases ---

@pytest.mark.asyncio
async def test_now_allowed(rule):
    passed, reason = await rule.evaluate("SELECT now()", SchemaContext())
    assert passed is True
    assert reason is None


@pytest.mark.asyncio
async def test_current_timestamp_allowed(rule):
    passed, reason = await rule.evaluate("SELECT current_timestamp", SchemaContext())
    assert passed is True
    assert reason is None


@pytest.mark.asyncio
async def test_literal_with_pg_allowed(rule):
    """Pattern inside a string literal must NOT trigger rejection."""
    passed, reason = await rule.evaluate("SELECT * FROM users WHERE name LIKE '%pg_%'", SchemaContext())
    assert passed is True
    assert reason is None
