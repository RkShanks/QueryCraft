"""T-230: Backend integration test for unsafe-pattern rule (FR-010f).

Tests that the full submit pipeline rejects known unsafe SQL patterns
enumerated in the platform unsafe-pattern catalog.
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
        ("SELECT pg_sleep(10)", "unsafe_pattern"),
        ("SELECT pg_read_file('/etc/passwd')", "unsafe_pattern"),
        ("SELECT pg_ls_dir('/')", "unsafe_pattern"),
        ("SELECT pg_terminate_backend(1)", "unsafe_pattern"),
        ("SELECT lo_export(1, '/tmp/x')", "unsafe_pattern"),
        ("COPY customer FROM PROGRAM 'rm -rf /'", "read_only"),
        ("SELECT * FROM dblink('host=evil.example.com', 'SELECT 1')", "schema_validation"),
        ("LISTEN evil_channel", "read_only"),
        ("SET ROLE postgres", "read_only"),
    ],
)
async def test_unsafe_pattern_rejected(
    authenticated_acceptance_client,
    db_session,
    query_submit_payload,
    bad_sql,
    expected_rule,
):
    """Unsafe patterns must be rejected before execution."""
    result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
    before = result.scalar()

    with patch(
        "app.api.v1.query.LLMProviderFactory.from_config",
        return_value=AsyncMock(generate_sql=AsyncMock(return_value=bad_sql)),
    ):
        response = await authenticated_acceptance_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload("Unsafe pattern"),
            headers={"origin": "http://test"},
        )

    assert response.status_code == 422
    data = response.json()
    assert data["message_key"] == "query.evaluator.rejected"
    violations = data["violations"]
    assert any(v["rule"] == expected_rule for v in violations)

    result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
    after = result.scalar()
    assert after == before
