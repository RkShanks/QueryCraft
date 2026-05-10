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
                ],
            ),
        ]
    )


@pytest.mark.asyncio
async def test_cross_schema_access_blocked(schema_with_customer):
    """SELECT * FROM secret_schema.customer must be rejected even if 'customer' exists in allowed schema."""
    rule = SchemaValidationRule()
    ok, msg = await rule.evaluate("SELECT * FROM secret_schema.customer", schema_with_customer)
    assert not ok
    assert "secret_schema" in (msg or "").lower() or "schema" in (msg or "").lower()
