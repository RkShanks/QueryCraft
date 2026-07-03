"""T-151: Acceptance test — multi-statement SQL blocked via submit pipeline.

Tests that the full submit pipeline rejects SQL containing more than one
statement with evaluator_rejected and a SingleStatementRule violation.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text


@pytest.mark.acceptance
@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bad_sql", "expected_rule"),
    [
        ("SELECT * FROM customer; DELETE FROM customer", "read_only"),
        ("SELECT 1; SELECT 2", "single_statement"),
        ("SELECT * FROM customer; -- inline comment", "read_only"),
    ],
)
async def test_multi_statement_sql_rejected(
    authenticated_acceptance_client,
    db_session,
    query_submit_payload,
    bad_sql,
    expected_rule,
):
    """Multi-statement SQL must be rejected before execution."""
    result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
    before = result.scalar()

    with patch(
        "app.api.v1.query.LLMProviderFactory.from_config",
        return_value=AsyncMock(generate_sql=AsyncMock(return_value=bad_sql)),
    ):
        response = await authenticated_acceptance_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload("Multi statement"),
            headers={"origin": "http://test"},
        )

    assert response.status_code == 422
    data = response.json()
    assert data["message_key"] == "query.evaluator.rejected"
    assert any(v["rule"] == expected_rule for v in data["violations"])

    result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
    after = result.scalar()
    assert after == before
