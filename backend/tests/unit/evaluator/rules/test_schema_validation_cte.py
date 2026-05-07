"""T-208: CTE handling regression test for SchemaValidationRule.

SchemaValidationRule must correctly resolve CTE aliases as virtual tables
so that valid CTE-based queries pass, while still rejecting CTEs that
reference non-existent base tables.
"""

import pytest

from app.evaluator.rules.schema_validation import SchemaValidationRule
from app.evaluator.schema_context import Column, SchemaContext, Table


@pytest.fixture
def schema_with_customer() -> SchemaContext:
    return SchemaContext(
        tables=[
            Table(
                name="customer",
                columns=[
                    Column(name="customer_id", type="integer", primary_key=True),
                    Column(name="first_name", type="text"),
                    Column(name="last_name", type="text"),
                    Column(name="active", type="boolean"),
                ],
            ),
            Table(
                name="payment",
                columns=[
                    Column(name="payment_id", type="integer", primary_key=True),
                    Column(name="customer_id", type="integer"),
                    Column(name="amount", type="numeric"),
                    Column(name="payment_date", type="timestamp"),
                ],
            ),
        ]
    )


@pytest.fixture
def rule() -> SchemaValidationRule:
    return SchemaValidationRule()


@pytest.mark.asyncio
async def test_cte_simple_passes(rule, schema_with_customer):
    """WITH ... SELECT * FROM cte_alias should pass."""
    sql = (
        "WITH active_customers AS (SELECT * FROM customer WHERE active = TRUE) "
        "SELECT * FROM active_customers"
    )
    passed, reason = await rule.evaluate(sql, schema_with_customer)
    assert passed is True, f"Expected pass, got: {reason}"


@pytest.mark.asyncio
async def test_cte_with_window_function_passes(rule, schema_with_customer):
    """CTE containing window functions should pass."""
    sql = (
        "WITH ranked AS (SELECT customer_id, ROW_NUMBER() OVER () AS rn FROM customer) "
        "SELECT * FROM ranked WHERE rn = 1"
    )
    passed, reason = await rule.evaluate(sql, schema_with_customer)
    assert passed is True, f"Expected pass, got: {reason}"


@pytest.mark.asyncio
async def test_recursive_cte_passes(rule, schema_with_customer):
    """Recursive CTE should pass (does not reference schema tables)."""
    sql = (
        "WITH RECURSIVE depth(n) AS ("
        "  SELECT 1 UNION SELECT n+1 FROM depth WHERE n < 5"
        ") SELECT * FROM depth"
    )
    passed, reason = await rule.evaluate(sql, schema_with_customer)
    assert passed is True, f"Expected pass, got: {reason}"


@pytest.mark.asyncio
async def test_cte_referencing_nonexistent_table_fails(rule, schema_with_customer):
    """CTE body referencing a nonexistent base table must still fail."""
    sql = (
        "WITH x AS (SELECT * FROM nonexistent) SELECT * FROM x"
    )
    passed, reason = await rule.evaluate(sql, schema_with_customer)
    assert passed is False, "Expected failure for CTE referencing nonexistent table"
    assert "nonexistent" in (reason or "")
