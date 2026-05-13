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
    "bad_sql,expected_fragment",
    [
        ("SELECT pg_sleep(10)", "pg_sleep"),
        ("SELECT pg_read_file('/etc/passwd')", "pg_read_file"),
        ("SELECT pg_ls_dir('/')", "pg_ls_dir"),
        ("SELECT pg_terminate_backend(1)", "pg_terminate_backend"),
        ("SELECT lo_export(1, '/tmp/x')", "lo_export"),
        ("COPY customer FROM PROGRAM 'rm -rf /'", "COPY"),
        ("SELECT * FROM dblink('host=evil.example.com', 'SELECT 1')", "dblink"),
        ("LISTEN evil_channel", "LISTEN"),
        ("SET ROLE postgres", "SET"),
    ],
)
async def test_unsafe_pattern_rejected(authenticated_acceptance_client, db_session, bad_sql, expected_fragment):
    """Unsafe patterns must be rejected before execution."""
    result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
    before = result.scalar()

    with patch(
        "app.api.v1.query.LLMProviderFactory.from_config",
        return_value=AsyncMock(generate_sql=AsyncMock(return_value=bad_sql)),
    ):
        response = await authenticated_acceptance_client.post(
            "/api/v1/query/submit",
            json={"question": "Unsafe pattern"},
            headers={"origin": "http://test"},
        )

    assert response.status_code == 422
    data = response.json()
    assert data["message_key"] == "query.evaluator.rejected"
    violations = data["violations"]
    assert any(v["rule"] == "unsafe_pattern" for v in violations)
    # Assert violation message includes the offending pattern
    detail_text = str(data)
    assert expected_fragment.lower() in detail_text.lower()

    result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
    after = result.scalar()
    assert after == before
