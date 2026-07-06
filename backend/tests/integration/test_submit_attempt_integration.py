"""T-212 test: submit_question + attempt_store integration regression test (FAIL).

Demonstrates gaps in current QueryService delegation to attempt_store
(Wave 3 audit OP-008, deferred to Wave 4 / T-212). Test asserts state
transitions PENDING→GENERATED→EVALUATED→EXECUTED|REJECTED|TIMEOUT and
attempt_id linkage on accepted_queries.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text


async def _clear_attempt_state(redis_client) -> None:
    keys = await redis_client.keys("attempt:*")
    keys.extend(await redis_client.keys("active_attempt:*"))
    if keys:
        await redis_client.delete(*keys)


@pytest.mark.integration
@pytest.mark.asyncio
class TestSubmitAttemptIntegration:
    """Integration tests for QueryService + AttemptStore (T-212)."""

    async def test_successful_submit_creates_attempt_with_states(
        self,
        authenticated_client,
        db_session,
        redis_client,
        query_submit_payload,
    ):
        """Happy path: attempt transitions PENDING→GENERATED→EVALUATED→EXECUTED."""
        await _clear_attempt_state(redis_client)

        with patch(
            "app.api.v1.query.LLMProviderFactory.from_config",
            return_value=AsyncMock(generate_sql=AsyncMock(return_value="SELECT 1 AS id")),
        ):
            response = await authenticated_client.post(
                "/api/v1/query/submit",
                json=query_submit_payload("What is one?"),
                headers={"origin": "http://test"},
            )

        assert response.status_code == 200
        data = response.json()
        attempt_id = data["attempt_id"]

        # Verify attempt in Redis with EXECUTED state
        raw = await redis_client.get(f"attempt:{attempt_id}")
        assert raw is not None
        attempt = json.loads(raw)
        assert attempt["state"] == "EXECUTED"
        assert attempt["sql"] == "SELECT 1 AS id"
        assert attempt["question"] == "What is one?"

        # Accept and verify attempt_id linkage in accepted_queries
        accept_resp = await authenticated_client.post(
            "/api/v1/query/accept",
            json={"attempt_id": attempt_id},
            headers={"origin": "http://test"},
        )
        assert accept_resp.status_code == 201

        result = await db_session.execute(
            text("SELECT attempt_id FROM accepted_queries WHERE question_text = 'What is one?'")
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == attempt_id

    async def test_evaluator_rejected_submit_creates_rejected_attempt(
        self,
        authenticated_client,
        db_session,
        redis_client,
        query_submit_payload,
    ):
        """Evaluator rejection: attempt transitions to REJECTED, no accepted_queries row."""
        await _clear_attempt_state(redis_client)
        before = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
        before_count = before.scalar()

        with patch(
            "app.api.v1.query.LLMProviderFactory.from_config",
            return_value=AsyncMock(generate_sql=AsyncMock(return_value="DROP TABLE users")),
        ):
            response = await authenticated_client.post(
                "/api/v1/query/submit",
                json=query_submit_payload("List customer names by city"),
                headers={"origin": "http://test"},
            )

        assert response.status_code == 422
        data = response.json()
        assert data["message_key"] == "query.evaluator.rejected"

        # Verify attempt exists in Redis with REJECTED state
        keys = await redis_client.keys("attempt:*")
        assert len(keys) == 1
        raw = await redis_client.get(keys[0])
        attempt = json.loads(raw)
        assert attempt["state"] == "REJECTED"

        # No accepted_queries row
        after = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
        assert after.scalar() == before_count

    async def test_timeout_submit_creates_timeout_attempt(
        self,
        authenticated_client,
        db_session,
        redis_client,
        query_submit_payload,
    ):
        """Timeout: attempt transitions to TIMEOUT, no accepted_queries row."""
        await _clear_attempt_state(redis_client)
        before = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
        before_count = before.scalar()

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
            patch(
                "app.source_db.adapters.PostgresAdapter.execute",
                side_effect=slow_execute,
            ),
        ):
            response = await authenticated_client.post(
                "/api/v1/query/submit",
                json=query_submit_payload("List customer names by city"),
                headers={"origin": "http://test"},
            )

        assert response.status_code == 504
        data = response.json()
        assert data["message_key"] == "error.timeout"

        # Verify attempt exists in Redis with TIMEOUT state
        keys = await redis_client.keys("attempt:*")
        assert len(keys) == 1
        raw = await redis_client.get(keys[0])
        attempt = json.loads(raw)
        assert attempt["state"] == "TIMEOUT"

        # No accepted_queries row
        after = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
        assert after.scalar() == before_count

    async def test_reject_validates_attempt_ownership(self, authenticated_client, redis_client):
        """Reject endpoint requires attempt_id to exist and be owned by session."""
        await _clear_attempt_state(redis_client)

        # Store an attempt for a different session
        await redis_client.set(
            "attempt:foreign-attempt",
            json.dumps(
                {
                    "attempt_id": "foreign-attempt",
                    "session_id": "different-session",
                    "sql": "SELECT 1",
                    "question": "Test",
                    "state": "EXECUTED",
                }
            ),
            ex=900,
        )

        response = await authenticated_client.post(
            "/api/v1/query/reject",
            json={"attempt_id": "foreign-attempt"},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 422
