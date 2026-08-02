"""T-109: Ephemeral attempt storage tests.

Tests store_attempt, get_attempt, delete_attempt with session ownership,
TTL expiry, and missing-key handling.
"""

import json
from datetime import date, datetime, time
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pydantic import BaseModel
from redis.asyncio import Redis

from app.core.attempt_store import EphemeralAttempt, delete_attempt, get_attempt, store_attempt
from app.core.exceptions import AttemptContextInvalid, AttemptNotFound, AttemptOwnershipViolation

CONNECTION_ID = UUID("550e8400-e29b-41d4-a716-446655440001")


class FakeAttempt(BaseModel):
    """Minimal attempt model for testing."""

    attempt_id: str
    session_id: str
    database_connection_id: str = str(CONNECTION_ID)
    sql: str
    question: str
    evaluator_result: dict | None = None
    executor_result: dict | None = None
    created_at: str = ""
    expires_at: str = ""


class TestAttemptStoreUnit:
    """Unit tests for attempt store."""

    async def test_store_attempt_writes_json_with_ttl(self):
        """store_attempt writes JSON with 15-min TTL."""
        redis = AsyncMock(spec=Redis)
        redis.set = AsyncMock(return_value=True)

        attempt = FakeAttempt(
            attempt_id="a1",
            session_id="s1",
            sql="SELECT 1",
            question="q1",
        )
        await store_attempt(attempt, "s1", redis)

        redis.set.assert_awaited_once()
        call_args = redis.set.call_args
        assert call_args.args[0] == "attempt:a1"
        assert call_args.kwargs["ex"] == 15 * 60

    async def test_get_attempt_returns_data_when_session_matches(self):
        """get_attempt returns attempt when session_id matches."""
        redis = AsyncMock(spec=Redis)
        raw = (
            '{"attempt_id":"a1","session_id":"s1","sql":"SELECT 1","question":"q1",'
            f'"database_connection_id":"{CONNECTION_ID}",'
            '"evaluator_result":null,"executor_result":null,"created_at":"","expires_at":""}'
        )
        redis.get = AsyncMock(return_value=raw)

        result = await get_attempt("a1", "s1", redis)
        assert result.attempt_id == "a1"
        assert result.session_id == "s1"

    async def test_get_attempt_raises_ownership_violation(self):
        """get_attempt with wrong session_id raises AttemptOwnershipViolation."""
        redis = AsyncMock(spec=Redis)
        raw = (
            '{"attempt_id":"a1","session_id":"s1","sql":"SELECT 1","question":"q1",'
            f'"database_connection_id":"{CONNECTION_ID}",'
            '"evaluator_result":null,"executor_result":null,"created_at":"","expires_at":""}'
        )
        redis.get = AsyncMock(return_value=raw)

        with pytest.raises(AttemptOwnershipViolation):
            await get_attempt("a1", "s2", redis)

    async def test_get_attempt_raises_not_found(self):
        """get_attempt for missing key raises AttemptNotFound."""
        redis = AsyncMock(spec=Redis)
        redis.get = AsyncMock(return_value=None)

        with pytest.raises(AttemptNotFound):
            await get_attempt("a1", "s1", redis)

    async def test_delete_attempt_removes_key(self):
        """delete_attempt removes the key."""
        redis = AsyncMock(spec=Redis)
        redis.delete = AsyncMock()

        await delete_attempt("a1", redis)
        redis.delete.assert_awaited_once_with("attempt:a1")

    async def test_store_attempt_serializes_decimal(self):
        """Decimal values in executor_result are serialized as floats."""
        redis = AsyncMock(spec=Redis)
        redis.set = AsyncMock(return_value=True)

        attempt = FakeAttempt(
            attempt_id="a1",
            session_id="s1",
            sql="SELECT 1",
            question="q1",
            executor_result={"rows": [[Decimal("10.50")]]},
        )
        await store_attempt(attempt, "s1", redis)

        call_args = redis.set.call_args
        stored = json.loads(call_args.args[1])
        assert stored["executor_result"]["rows"][0][0] == 10.50

    async def test_store_attempt_serializes_datetime(self):
        """datetime/date/time values in executor_result are serialized as ISO strings."""
        redis = AsyncMock(spec=Redis)
        redis.set = AsyncMock(return_value=True)

        attempt = FakeAttempt(
            attempt_id="a1",
            session_id="s1",
            sql="SELECT 1",
            question="q1",
            executor_result={
                "rows": [[datetime(2026, 5, 23, 12, 0, 0), date(2026, 5, 23), time(12, 30, 0)]],
            },
        )
        await store_attempt(attempt, "s1", redis)

        call_args = redis.set.call_args
        stored = json.loads(call_args.args[1])
        assert stored["executor_result"]["rows"][0][0] == "2026-05-23T12:00:00"
        assert stored["executor_result"]["rows"][0][1] == "2026-05-23"
        assert stored["executor_result"]["rows"][0][2] == "12:30:00"

    async def test_connection_context_round_trips_as_canonical_uuid(self):
        """The submit-time source is canonical, immutable attempt context."""
        redis = AsyncMock(spec=Redis)
        attempt = EphemeralAttempt(
            attempt_id="a1",
            session_id="s1",
            user_id="u1",
            database_connection_id=str(CONNECTION_ID).upper(),
        )

        await store_attempt(attempt, "s1", redis)
        stored_json = redis.set.await_args.args[1]
        redis.get = AsyncMock(return_value=stored_json)

        restored = await get_attempt("a1", "s1", redis)

        assert restored.database_connection_id == CONNECTION_ID
        assert json.loads(stored_json)["database_connection_id"] == str(CONNECTION_ID)

    @pytest.mark.parametrize(
        "stored_context",
        [
            {},
            {"database_connection_id": "not-a-uuid"},
        ],
    )
    async def test_missing_or_malformed_connection_context_fails_closed(self, stored_context):
        """Legacy or corrupt Redis attempts cannot select a fallback source."""
        redis = AsyncMock(spec=Redis)
        redis.get = AsyncMock(
            return_value=json.dumps(
                {
                    "attempt_id": "a1",
                    "session_id": "s1",
                    "user_id": "u1",
                    **stored_context,
                }
            )
        )

        with pytest.raises(AttemptContextInvalid):
            await get_attempt("a1", "s1", redis)

    async def test_connection_continuity_adds_no_sensitive_context_fields(self):
        """Continuity stores only the connection UUID, never connection internals."""
        redis = AsyncMock(spec=Redis)
        attempt = EphemeralAttempt(
            attempt_id="a1",
            session_id="s1",
            user_id="u1",
            database_connection_id=CONNECTION_ID,
        )

        await store_attempt(attempt, "s1", redis)
        stored = json.loads(redis.set.await_args.args[1])

        assert {
            "credentials",
            "connection_string",
            "schema_context",
            "role_policy",
            "row_filters",
            "column_masks",
            "source_rows",
        }.isdisjoint(stored)


@pytest.mark.integration
class TestAttemptStoreIntegration:
    """Integration tests with real redis fixture."""

    async def test_store_and_get_with_real_redis(self, redis_client):
        """Store and retrieve with testcontainers redis."""
        attempt = FakeAttempt(
            attempt_id="a2",
            session_id="s2",
            sql="SELECT 2",
            question="q2",
        )
        await store_attempt(attempt, "s2", redis_client)
        result = await get_attempt("a2", "s2", redis_client)
        assert result.sql == "SELECT 2"

    async def test_ownership_violation_with_real_redis(self, redis_client):
        """Cross-session get raises ownership violation."""
        attempt = FakeAttempt(
            attempt_id="a3",
            session_id="s3",
            sql="SELECT 3",
            question="q3",
        )
        await store_attempt(attempt, "s3", redis_client)
        with pytest.raises(AttemptOwnershipViolation):
            await get_attempt("a3", "other", redis_client)
