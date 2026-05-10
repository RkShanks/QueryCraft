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


@pytest.mark.asyncio
@pytest.mark.parametrize("sql", [
    'SELECT "dblink"(\'dbname=postgres\', \'DROP TABLE users;\')',
    'SELECT "pg_sleep"(10)',
    'SELECT "pg_read_file"(\'/etc/passwd\')',
    'SELECT "PG_SLEEP"(10)',  # mixed case quoted
])
async def test_quoted_identifier_bypass_blocked(rule, sql):
    ok, msg = await rule.evaluate(sql, SchemaContext())
    assert not ok
    assert msg is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("func", [
    "pg_advisory_lock", "pg_advisory_unlock", "pg_advisory_lock_shared",
    "pg_advisory_xact_lock", "pg_try_advisory_lock", "pg_try_advisory_xact_lock",
    "set_config", "current_setting",
    "pg_promote", "pg_switch_wal",
    "pg_backup_start", "pg_backup_stop",
])
async def test_extended_unsafe_catalog(rule, func):
    ok, msg = await rule.evaluate(f"SELECT {func}(1)", SchemaContext())
    assert not ok


@pytest.mark.asyncio
async def test_unsafe_pattern_add_pattern_extends_catalog(rule):
    rule.add_pattern("custom_unsafe_fn")
    ok, _ = await rule.evaluate("SELECT custom_unsafe_fn(1)", SchemaContext())
    assert not ok


@pytest.mark.asyncio
@pytest.mark.parametrize("func", [
    "version", "pg_version_num", "inet_server_addr", "pg_postmaster_start_time",
    "current_database", "current_user", "session_user",
])
async def test_metadata_disclosure_blocked(rule, func):
    ok, _ = await rule.evaluate(f"SELECT {func}()", SchemaContext())
    assert not ok
