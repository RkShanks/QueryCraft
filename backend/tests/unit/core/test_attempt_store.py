"""T-109: Ephemeral attempt storage tests.

Tests store_attempt, get_attempt, delete_attempt with session ownership,
TTL expiry, and missing-key handling.
"""

import json
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pydantic import ValidationError
from redis.asyncio import Redis

from app.core.attempt_store import EphemeralAttempt, delete_attempt, get_attempt, store_attempt
from app.core.exceptions import AttemptContextInvalid, AttemptNotFound, AttemptOwnershipViolation

CONNECTION_ID = UUID("550e8400-e29b-41d4-a716-446655440001")
ATTEMPT_ID = "550e8400-e29b-41d4-a716-446655440010"
OTHER_ATTEMPT_ID = "550e8400-e29b-41d4-a716-446655440011"
USER_ID = "550e8400-e29b-41d4-a716-446655440020"
OTHER_USER_ID = "550e8400-e29b-41d4-a716-446655440021"
CHAT_SESSION_ID = "550e8400-e29b-41d4-a716-446655440030"
HTTP_SESSION_ID = "attempt-owner-session"


class _ReplaceBeforeAttemptCleanupRedis:
    def __init__(self, redis_client, attempt_key: str, replacement_json: str):
        self._redis = redis_client
        self._attempt_key = attempt_key
        self._replacement_json = replacement_json

    def __getattr__(self, name: str):
        return getattr(self._redis, name)

    async def eval(self, script: str, numkeys: int, *keys_and_args: str):
        await self._redis.set(self._attempt_key, self._replacement_json, ex=900)
        return await self._redis.eval(script, numkeys, *keys_and_args)


async def _serialized_owned_attempt() -> str:
    redis = AsyncMock(spec=Redis)
    redis.set = AsyncMock(return_value=True)
    await store_attempt(
        EphemeralAttempt(
            attempt_id=ATTEMPT_ID,
            session_id=HTTP_SESSION_ID,
            chat_session_id=CHAT_SESSION_ID,
            user_id=USER_ID,
            database_connection_id=CONNECTION_ID,
            state="PENDING",
        ),
        HTTP_SESSION_ID,
        redis,
    )
    return redis.set.await_args.args[1]


class TestAttemptStoreUnit:
    """Unit tests for attempt store."""

    async def test_store_attempt_writes_json_with_ttl(self):
        """store_attempt writes JSON with 15-min TTL."""
        redis = AsyncMock(spec=Redis)
        redis.set = AsyncMock(return_value=True)

        attempt = EphemeralAttempt(
            attempt_id=ATTEMPT_ID,
            session_id=HTTP_SESSION_ID,
            user_id=USER_ID,
            database_connection_id=CONNECTION_ID,
            sql="SELECT 1",
            question="q1",
        )
        await store_attempt(attempt, HTTP_SESSION_ID, redis)

        redis.set.assert_awaited_once()
        call_args = redis.set.call_args
        assert call_args.args[0] == f"attempt:{ATTEMPT_ID}"
        assert call_args.kwargs["ex"] == 15 * 60

    async def test_get_attempt_returns_data_when_session_matches(self):
        """get_attempt returns attempt when session_id matches."""
        redis = AsyncMock(spec=Redis)
        redis.set = AsyncMock(return_value=True)
        attempt = EphemeralAttempt(
            attempt_id=ATTEMPT_ID,
            session_id=HTTP_SESSION_ID,
            user_id=USER_ID,
            database_connection_id=CONNECTION_ID,
            sql="SELECT 1",
            question="q1",
        )
        await store_attempt(attempt, HTTP_SESSION_ID, redis)
        redis.get = AsyncMock(return_value=redis.set.await_args.args[1])

        result = await get_attempt(ATTEMPT_ID, HTTP_SESSION_ID, USER_ID, redis)
        assert result.attempt_id == ATTEMPT_ID
        assert result.session_id == HTTP_SESSION_ID

    async def test_get_attempt_raises_ownership_violation(self):
        """get_attempt with wrong session_id raises AttemptOwnershipViolation."""
        redis = AsyncMock(spec=Redis)
        redis.set = AsyncMock(return_value=True)
        attempt = EphemeralAttempt(
            attempt_id=ATTEMPT_ID,
            session_id=HTTP_SESSION_ID,
            user_id=USER_ID,
            database_connection_id=CONNECTION_ID,
            sql="SELECT 1",
            question="q1",
        )
        await store_attempt(attempt, HTTP_SESSION_ID, redis)
        redis.get = AsyncMock(return_value=redis.set.await_args.args[1])

        with pytest.raises(AttemptOwnershipViolation):
            await get_attempt(ATTEMPT_ID, "other-session", USER_ID, redis)

    async def test_get_attempt_raises_not_found(self):
        """get_attempt for missing key raises AttemptNotFound."""
        redis = AsyncMock(spec=Redis)
        redis.get = AsyncMock(return_value=None)

        with pytest.raises(AttemptNotFound):
            await get_attempt(ATTEMPT_ID, HTTP_SESSION_ID, USER_ID, redis)

    async def test_delete_attempt_removes_key(self):
        """delete_attempt removes the key."""
        redis = AsyncMock(spec=Redis)
        redis.delete = AsyncMock()

        await delete_attempt("a1", redis)
        redis.delete.assert_awaited_once_with("attempt:a1")

    async def test_attempt_state_omits_result_payload(self):
        """Attempt metadata never reserves a Redis field for source rows."""
        redis = AsyncMock(spec=Redis)
        redis.set = AsyncMock(return_value=True)

        attempt = EphemeralAttempt(
            attempt_id="a1",
            session_id="s1",
            database_connection_id=CONNECTION_ID,
            sql="SELECT 1",
            question="q1",
        )
        await store_attempt(attempt, "s1", redis)

        stored = json.loads(redis.set.await_args.args[1])
        assert "executor_result" not in stored

    def test_attempt_schema_rejects_result_payload(self):
        """Result rows cannot enter attempt state through model construction."""
        with pytest.raises(ValidationError):
            EphemeralAttempt(
                attempt_id="a1",
                session_id="s1",
                database_connection_id=CONNECTION_ID,
                executor_result={"rows": []},
            )

    async def test_connection_context_round_trips_as_canonical_uuid(self):
        """The submit-time source is canonical, immutable attempt context."""
        redis = AsyncMock(spec=Redis)
        redis.set = AsyncMock(return_value=True)
        attempt = EphemeralAttempt(
            attempt_id=ATTEMPT_ID,
            session_id=HTTP_SESSION_ID,
            user_id=USER_ID,
            database_connection_id=str(CONNECTION_ID).upper(),
        )

        await store_attempt(attempt, HTTP_SESSION_ID, redis)
        stored_json = redis.set.await_args.args[1]
        redis.get = AsyncMock(return_value=stored_json)

        restored = await get_attempt(ATTEMPT_ID, HTTP_SESSION_ID, USER_ID, redis)

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
        redis.set = AsyncMock(return_value=True)
        await store_attempt(
            EphemeralAttempt(
                attempt_id=ATTEMPT_ID,
                session_id=HTTP_SESSION_ID,
                user_id=USER_ID,
                database_connection_id=CONNECTION_ID,
            ),
            HTTP_SESSION_ID,
            redis,
        )
        stored = json.loads(redis.set.await_args.args[1])
        stored.pop("database_connection_id", None)
        stored.update(stored_context)
        redis.get = AsyncMock(return_value=json.dumps(stored))
        redis.delete = AsyncMock(return_value=1)
        redis.eval = AsyncMock(return_value=1)

        with pytest.raises(AttemptContextInvalid):
            await get_attempt(ATTEMPT_ID, HTTP_SESSION_ID, USER_ID, redis)

    async def test_connection_continuity_adds_no_sensitive_context_fields(self):
        """Continuity stores only the connection UUID, never connection internals."""
        redis = AsyncMock(spec=Redis)
        redis.set = AsyncMock(return_value=True)
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
            "executor_result",
        }.isdisjoint(stored)

    @pytest.mark.parametrize(
        ("field", "invalid_value"),
        [
            pytest.param("attempt_id", "not-a-uuid", id="attempt-id-invalid"),
            pytest.param("attempt_id", ATTEMPT_ID.upper(), id="attempt-id-noncanonical"),
            pytest.param("attempt_id", OTHER_ATTEMPT_ID, id="attempt-id-key-mismatch"),
            pytest.param("user_id", "not-a-uuid", id="user-id-invalid"),
            pytest.param("user_id", USER_ID.upper(), id="user-id-noncanonical"),
            pytest.param("chat_session_id", "not-a-uuid", id="chat-session-invalid"),
            pytest.param("database_connection_id", "not-a-uuid", id="source-context-invalid"),
            pytest.param("state", "SUCCESS", id="state-unknown"),
            pytest.param("attempt_number", 0, id="attempt-number-zero"),
            pytest.param("attempt_number", 1.5, id="attempt-number-float"),
            pytest.param("attempt_number", "2", id="attempt-number-string"),
            pytest.param("question", {}, id="question-object"),
            pytest.param("sql", [], id="sql-list"),
            pytest.param("llm_provider", {}, id="provider-object"),
            pytest.param("created_at", [], id="created-at-list"),
            pytest.param("expires_at", {}, id="expires-at-object"),
        ],
    )
    async def test_semantic_corruption_is_constant_and_only_owned_state_is_deleted(self, field, invalid_value):
        stored = json.loads(await _serialized_owned_attempt())
        stored[field] = invalid_value
        raw_attempt = json.dumps(stored)
        redis = AsyncMock(spec=Redis)
        redis.get = AsyncMock(return_value=raw_attempt)
        redis.eval = AsyncMock(return_value=1)

        with pytest.raises(AttemptContextInvalid) as exc_info:
            await get_attempt(ATTEMPT_ID, HTTP_SESSION_ID, USER_ID, redis)

        assert str(exc_info.value) == "No active query result to act on"
        if field == "user_id":
            redis.eval.assert_not_awaited()
        else:
            redis.eval.assert_awaited_once()
        redis.delete.assert_not_called()

    @pytest.mark.parametrize(
        "missing_field",
        [
            "attempt_id",
            "user_id",
            "database_connection_id",
            "state",
            "attempt_number",
            "question",
            "sql",
            "evaluator_result",
            "llm_provider",
            "created_at",
            "expires_at",
        ],
    )
    async def test_owned_attempt_missing_required_field_fails_closed(self, missing_field):
        stored = json.loads(await _serialized_owned_attempt())
        stored.pop(missing_field)
        raw_attempt = json.dumps(stored)
        redis = AsyncMock(spec=Redis)
        redis.get = AsyncMock(return_value=raw_attempt)
        redis.eval = AsyncMock(return_value=1)

        with pytest.raises(AttemptContextInvalid):
            await get_attempt(ATTEMPT_ID, HTTP_SESSION_ID, USER_ID, redis)

    async def test_wrong_user_is_rejected_before_decryption_or_cleanup(self):
        stored = json.loads(await _serialized_owned_attempt())
        stored["question"] = "invalid-ciphertext"
        redis = AsyncMock(spec=Redis)
        redis.get = AsyncMock(return_value=json.dumps(stored))

        with pytest.raises(AttemptOwnershipViolation):
            await get_attempt(ATTEMPT_ID, HTTP_SESSION_ID, OTHER_USER_ID, redis)

        redis.eval.assert_not_called()
        redis.delete.assert_not_called()

    async def test_unowned_invalid_document_is_not_destructively_cleaned(self):
        redis = AsyncMock(spec=Redis)
        redis.get = AsyncMock(return_value="[]")

        with pytest.raises(AttemptContextInvalid):
            await get_attempt(ATTEMPT_ID, HTTP_SESSION_ID, USER_ID, redis)

        redis.eval.assert_not_called()
        redis.delete.assert_not_called()

    async def test_rejected_state_requires_structured_evaluator_result(self):
        stored = json.loads(await _serialized_owned_attempt())
        stored["state"] = "REJECTED"
        raw_attempt = json.dumps(stored)
        redis = AsyncMock(spec=Redis)
        redis.get = AsyncMock(return_value=raw_attempt)
        redis.eval = AsyncMock(return_value=1)

        with pytest.raises(AttemptContextInvalid):
            await get_attempt(ATTEMPT_ID, HTTP_SESSION_ID, USER_ID, redis)

        redis.eval.assert_awaited_once()


@pytest.mark.integration
class TestAttemptStoreIntegration:
    """Integration tests with real redis fixture."""

    async def test_store_and_get_with_real_redis(self, redis_client):
        """Store and retrieve with testcontainers redis."""
        attempt = EphemeralAttempt(
            attempt_id=ATTEMPT_ID,
            session_id=HTTP_SESSION_ID,
            user_id=USER_ID,
            database_connection_id=CONNECTION_ID,
            sql="SELECT 2",
            question="q2",
        )
        await store_attempt(attempt, HTTP_SESSION_ID, redis_client)
        result = await get_attempt(ATTEMPT_ID, HTTP_SESSION_ID, USER_ID, redis_client)
        assert result.sql == "SELECT 2"

    async def test_ownership_violation_with_real_redis(self, redis_client):
        """Cross-session get raises ownership violation."""
        attempt = EphemeralAttempt(
            attempt_id=ATTEMPT_ID,
            session_id=HTTP_SESSION_ID,
            user_id=USER_ID,
            database_connection_id=CONNECTION_ID,
            sql="SELECT 3",
            question="q3",
        )
        await store_attempt(attempt, HTTP_SESSION_ID, redis_client)
        with pytest.raises(AttemptOwnershipViolation):
            await get_attempt(ATTEMPT_ID, "other", USER_ID, redis_client)

    async def test_corrupt_owned_attempt_is_removed_and_later_valid_state_recovers(self, redis_client):
        """Owned semantic corruption is removed without a process restart."""
        attempt = EphemeralAttempt(
            attempt_id=ATTEMPT_ID,
            session_id=HTTP_SESSION_ID,
            chat_session_id=CHAT_SESSION_ID,
            user_id=USER_ID,
            database_connection_id=CONNECTION_ID,
            state="EXECUTED",
        )
        await store_attempt(attempt, attempt.session_id, redis_client)
        attempt_key = f"attempt:{ATTEMPT_ID}"
        corrupt_document = json.loads(await redis_client.get(attempt_key))
        corrupt_document["attempt_number"] = 0
        await redis_client.set(attempt_key, json.dumps(corrupt_document), ex=900)

        with pytest.raises(AttemptContextInvalid):
            await get_attempt(ATTEMPT_ID, attempt.session_id, USER_ID, redis_client)

        assert await redis_client.exists(attempt_key) == 0
        await store_attempt(attempt, attempt.session_id, redis_client)
        recovered = await get_attempt(ATTEMPT_ID, attempt.session_id, USER_ID, redis_client)
        assert recovered.state == "EXECUTED"

    async def test_stale_corruption_cleanup_preserves_valid_replacement(self, redis_client):
        """Compare-delete cannot remove a concurrently replaced valid attempt."""
        attempt = EphemeralAttempt(
            attempt_id=ATTEMPT_ID,
            session_id=HTTP_SESSION_ID,
            chat_session_id=CHAT_SESSION_ID,
            user_id=USER_ID,
            database_connection_id=CONNECTION_ID,
            state="EXECUTED",
        )
        await store_attempt(attempt, attempt.session_id, redis_client)
        attempt_key = f"attempt:{ATTEMPT_ID}"
        replacement_json = await redis_client.get(attempt_key)
        corrupt_document = json.loads(replacement_json)
        corrupt_document["state"] = "SUCCESS"
        await redis_client.set(attempt_key, json.dumps(corrupt_document), ex=900)
        replacing_redis = _ReplaceBeforeAttemptCleanupRedis(redis_client, attempt_key, replacement_json)

        with pytest.raises(AttemptContextInvalid):
            await get_attempt(ATTEMPT_ID, attempt.session_id, USER_ID, replacing_redis)

        assert await redis_client.get(attempt_key) == replacement_json
        recovered = await get_attempt(ATTEMPT_ID, attempt.session_id, USER_ID, redis_client)
        assert recovered.state == "EXECUTED"
