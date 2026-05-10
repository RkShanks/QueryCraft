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


@pytest.mark.asyncio
@pytest.mark.parametrize("sql", [
    "SELECT 1 UNION SELECT 2",
    "SELECT 1 UNION ALL SELECT 2",
    "SELECT 1 INTERSECT SELECT 1",
    "SELECT 1 EXCEPT SELECT 2",
    # Recursive CTE with UNION
    "WITH RECURSIVE n(i) AS (SELECT 1 UNION SELECT i+1 FROM n WHERE i < 5) SELECT * FROM n",
])
async def test_set_operations_pass_read_only(sql):
    rule = ReadOnlyRule()
    ok, _ = await rule.evaluate(sql, None)
    assert ok, f"{sql} is read-only and must pass"


@pytest.mark.asyncio
async def test_union_with_update_branch_blocked():
    rule = ReadOnlyRule()
    ok, msg = await rule.evaluate("SELECT 1 UNION SELECT * FROM (UPDATE customer SET active = FALSE) AS u", None)
    assert not ok, "UNION containing UPDATE branch must be blocked"
