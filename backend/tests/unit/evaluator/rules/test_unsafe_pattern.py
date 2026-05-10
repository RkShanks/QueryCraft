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
