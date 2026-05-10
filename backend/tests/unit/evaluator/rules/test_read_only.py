import pytest
from app.evaluator.rules.read_only import ReadOnlyRule


@pytest.mark.asyncio
@pytest.mark.parametrize("sql", [
    "SELECT * FROM customer FOR UPDATE",
    "SELECT * FROM customer FOR SHARE",
    "SELECT * FROM customer FOR NO KEY UPDATE",
    "SELECT * FROM customer FOR KEY SHARE",
])
async def test_select_for_lock_blocked(sql):
    rule = ReadOnlyRule()
    ok, msg = await rule.evaluate(sql, None)
    assert not ok, f"{sql} should be blocked but passed"
