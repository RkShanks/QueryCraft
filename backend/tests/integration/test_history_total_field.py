"""T-161b: HistoryListResponse.total is populated on first-page-only (no cursor)."""

import pytest
import pytest_asyncio
from sqlalchemy import text


@pytest_asyncio.fixture
async def seeded_history(async_engine_fixture, authenticated_client):
    """Insert ~5 accepted_queries rows for the authenticated admin user."""
    async with async_engine_fixture.connect() as conn:
        result = await conn.execute(text("SELECT id FROM users WHERE username = 'admin'"))
        row = result.fetchone()
        user_id = str(row.id)

        result = await conn.execute(text("SELECT id FROM database_connections LIMIT 1"))
        row = result.fetchone()
        db_conn_id = str(row.id) if row else "00000000-0000-0000-0000-000000000001"

        for i in range(5):
            await conn.execute(
                text(
                    """
                    INSERT INTO accepted_queries (
                        user_id, database_connection_id, question_text,
                        generated_sql, llm_provider, accepted_at
                    ) VALUES (
                        :user_id, :db_conn_id, :question, :sql, 'ollama',
                        now() - (:offset || ' minutes')::interval
                    )
                    """
                ),
                {
                    "user_id": user_id,
                    "db_conn_id": db_conn_id,
                    "question": f"Test question {i}",
                    "sql": f"SELECT {i}",
                    "offset": i,
                },
            )
        await conn.commit()
    yield


@pytest.mark.asyncio
@pytest.mark.integration
async def test_history_first_page_includes_total(authenticated_client, seeded_history):
    """First-page request (no cursor) MUST include `total`."""
    r = await authenticated_client.get("/api/v1/history")
    assert r.status_code == 200
    body = r.json()
    assert "total" in body
    assert isinstance(body["total"], int)
    assert body["total"] >= 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_history_subsequent_page_omits_total(authenticated_client, seeded_history):
    """Subsequent page requests (with cursor) MAY omit `total` (perf optimization)."""
    r = await authenticated_client.get("/api/v1/history?cursor=abc")
    assert r.status_code == 200
    body = r.json()
    # Either omitted or present — both acceptable per spec
    if "total" in body:
        assert isinstance(body["total"], int)
