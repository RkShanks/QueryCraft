import pytest
from app.evaluator.rules.unsafe_pattern import UnsafePatternRule


@pytest.mark.asyncio
@pytest.mark.parametrize("sql", [
    'SELECT "dblink"(\'dbname=postgres\', \'DROP TABLE users;\')',
    'SELECT "pg_sleep"(10)',
    'SELECT "pg_read_file"(\'/etc/passwd\')',
    'SELECT "PG_SLEEP"(10)',  # mixed case quoted
])
async def test_quoted_identifier_bypass_blocked(sql):
    rule = UnsafePatternRule()
    ok, msg = await rule.evaluate(sql, None)
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
async def test_extended_unsafe_catalog(func):
    rule = UnsafePatternRule()
    ok, msg = await rule.evaluate(f"SELECT {func}(1)", None)
    assert not ok


@pytest.mark.asyncio
async def test_unsafe_pattern_add_pattern_extends_catalog():
    rule = UnsafePatternRule()
    rule.add_pattern("custom_unsafe_fn")
    ok, _ = await rule.evaluate("SELECT custom_unsafe_fn(1)", None)
    assert not ok
