"""T-153: Acceptance test — query timeout cancellation and cleanup.

Verifies FR-012 (timeout enforcement), SC-011 (timeout behavior measurement).
Asserts: timeout response shape, no DB write, no orphan attempt, no leaked connection.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text


@pytest.mark.acceptance
@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_timeout_cancellation_and_cleanup(
    authenticated_acceptance_client,
    db_session,
    redis_client,
    query_submit_payload,
):
    """Slow query must timeout, return 504, and leave no orphan state."""
    result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
    before = result.scalar()

    # Ensure Redis is clean
    await redis_client.flushdb()

    # Patch executor to sleep longer than the 30-second timeout
    async def slow_execute(*args, **kwargs):
        await asyncio.sleep(60)
        return [], []

    with (
        patch(
            "app.api.v1.query.LLMProviderFactory.from_config",
            return_value=AsyncMock(generate_sql=AsyncMock(return_value="SELECT 1")),
        ),
        patch(
            "app.api.v1.query._source_db_executor.execute",
            side_effect=slow_execute,
        ),
    ):
        response = await authenticated_acceptance_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload("Slow query"),
            headers={"origin": "http://test"},
        )

    # 1. Timeout response
    assert response.status_code == 504
    data = response.json()
    assert data["message_key"] == "error.timeout"

    # 2. No row written to accepted_queries
    result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
    after = result.scalar()
    assert after == before

    # 3. No orphan attempt in Redis
    keys = await redis_client.keys("attempt:*")
    assert len(keys) == 0

    # 4. Lock released — a second request should succeed immediately
    with patch(
        "app.api.v1.query.LLMProviderFactory.from_config",
        return_value=AsyncMock(generate_sql=AsyncMock(return_value="SELECT 1 AS id")),
    ):
        recovery = await authenticated_acceptance_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload("Fast query"),
            headers={"origin": "http://test"},
        )
    assert recovery.status_code == 200
    recovery_data = recovery.json()
    assert recovery_data["kind"] == "result"

    # 5. Connection pool not exhausted (best-effort check)
    from app.api.v1.query import _source_db_connector

    if _source_db_connector._pool is not None:
        size = _source_db_connector._pool.get_size()
        idle = _source_db_connector._pool.get_idle_size()
        assert idle == size, f"Leaked connections: {size - idle} of {size} not idle"
