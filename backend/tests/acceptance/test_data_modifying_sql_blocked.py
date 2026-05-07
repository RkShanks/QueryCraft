"""T-149: Acceptance test — data-modifying SQL blocked via submit pipeline.

Tests that the full submit pipeline rejects INSERT, UPDATE, DELETE, TRUNCATE,
DROP, and ALTER statements with evaluator_rejected and a ReadOnlyRule violation.
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
        "DELETE FROM customers",
        "UPDATE customers SET email = ''",
        "INSERT INTO customers (first_name) VALUES ('test')",
        "TRUNCATE customers",
        "DROP TABLE customers",
        "ALTER TABLE customers ADD COLUMN x INT",
    ],
)
async def test_data_modifying_sql_rejected(
    authenticated_acceptance_client, db_session, bad_sql
):
    """Data-modifying SQL must be rejected before execution."""
    # Count accepted_queries before
    result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
    before = result.scalar()

    with patch(
        "app.api.v1.query.LLMProviderFactory.from_config",
        return_value=AsyncMock(generate_sql=AsyncMock(return_value=bad_sql)),
    ):
        response = await authenticated_acceptance_client.post(
            "/api/v1/query/submit",
            json={"question": "Do something bad"},
            headers={"origin": "http://test"},
        )

    assert response.status_code == 422
    data = response.json()
    assert data["message_key"] == "query.evaluator.rejected"
    assert any(v["rule"] == "read_only" for v in data["violations"])

    # No row written to accepted_queries
    result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
    after = result.scalar()
    assert after == before
