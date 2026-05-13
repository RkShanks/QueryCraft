"""T-152: Acceptance test — valid read-only SELECT and CTE pass evaluator + execute.

Tests that the full submit pipeline accepts and executes valid SELECT queries,
including CTE-based queries (requires T-208 fix).
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text


@pytest.mark.acceptance
@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "good_sql,expected_min_rows",
    [
        ("SELECT * FROM customer LIMIT 10", 1),
        ("SELECT first_name, last_name FROM customer WHERE active = TRUE LIMIT 5", 1),
        (
            "WITH recent AS (SELECT * FROM payment ORDER BY payment_date DESC LIMIT 100) "
            "SELECT customer_id, SUM(amount) FROM recent GROUP BY customer_id",
            1,
        ),
        (
            "SELECT customer.first_name, address.address FROM customer "
            "JOIN address ON customer.address_id = address.address_id LIMIT 10",
            1,
        ),
    ],
)
async def test_valid_select_passes(authenticated_acceptance_client, db_session, good_sql, expected_min_rows):
    """Valid read-only SQL must pass evaluator, execute, and return results."""
    result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
    before = result.scalar()

    with patch(
        "app.api.v1.query.LLMProviderFactory.from_config",
        return_value=AsyncMock(generate_sql=AsyncMock(return_value=good_sql)),
    ):
        response = await authenticated_acceptance_client.post(
            "/api/v1/query/submit",
            json={"question": "Valid query"},
            headers={"origin": "http://test"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["kind"] == "result"
    assert data["row_count"] >= expected_min_rows
    assert data["generated_sql"] == good_sql

    # Accept the query to persist it
    attempt_id = data["attempt_id"]
    accept_resp = await authenticated_acceptance_client.post(
        "/api/v1/query/accept",
        json={"attempt_id": attempt_id},
        headers={"origin": "http://test"},
    )
    assert accept_resp.status_code == 201

    # Row written to accepted_queries
    result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
    after = result.scalar()
    assert after == before + 1
