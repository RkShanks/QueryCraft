"""T-150: Acceptance test — schema-invalid SQL blocked via submit pipeline.

Tests that the full submit pipeline rejects SQL referencing unknown tables,
columns, or schemas with evaluator_rejected and a sanitized SchemaValidationRule
violation.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text


@pytest.mark.acceptance
@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_sql",
    [
        "SELECT * FROM nonexistent_table",
        "SELECT nonexistent_column FROM customer",
        "SELECT * FROM customer JOIN ghost ON customer.customer_id = ghost.id",
        "SELECT * FROM customer.fake_schema",
    ],
)
async def test_schema_invalid_sql_rejected(
    authenticated_acceptance_client,
    db_session,
    query_submit_payload,
    bad_sql,
):
    """Schema-invalid SQL must be rejected before execution."""
    result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
    before = result.scalar()

    with patch(
        "app.api.v1.query.LLMProviderFactory.from_config",
        return_value=AsyncMock(generate_sql=AsyncMock(return_value=bad_sql)),
    ):
        response = await authenticated_acceptance_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload("Bad schema query"),
            headers={"origin": "http://test"},
        )

    assert response.status_code == 422
    data = response.json()
    assert data["message_key"] == "query.evaluator.rejected"
    violations = data["violations"]
    assert any(v["rule"] == "schema_validation" for v in violations)

    result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
    after = result.scalar()
    assert after == before
