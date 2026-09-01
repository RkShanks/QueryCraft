"""Regression coverage for plaintext attempt retention (CHUNK-28)."""

import base64
import json
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from redis.asyncio import Redis

from app.core.attempt_store import EphemeralAttempt, get_attempt, store_attempt
from app.core.encryption import decrypt, encrypt
from app.core.exceptions import AttemptContextInvalid

CONNECTION_ID = UUID("550e8400-e29b-41d4-a716-446655440001")
ATTEMPT_ID = "550e8400-e29b-41d4-a716-446655440012"
USER_ID = "550e8400-e29b-41d4-a716-446655440022"
CHAT_SESSION_ID = "550e8400-e29b-41d4-a716-446655440032"


async def test_serialized_attempt_does_not_retain_user_canary() -> None:
    """A pending attempt never stores a plaintext user question."""
    redis = AsyncMock(spec=Redis)
    redis.set = AsyncMock(return_value=True)
    canary = "chunk28-user-canary"
    attempt = EphemeralAttempt(
        attempt_id="privacy-a1",
        session_id="privacy-session",
        database_connection_id=CONNECTION_ID,
        question=canary,
    )

    await store_attempt(attempt, attempt.session_id, redis)

    serialized = redis.set.await_args.args[1]
    plaintext_present = canary in serialized
    encoded_plaintext_present = canary.encode() in json.dumps(serialized).encode()
    assert plaintext_present is False, "serialized attempt contains plaintext question"
    assert encoded_plaintext_present is False, "serialized attempt contains encoded plaintext question"


def _encrypted_text(text: str, purpose: str, key: str, version: int = 1) -> str:
    return encrypt(
        json.dumps({"purpose": purpose, "version": version, "text": text}),
        key,
    )


def _serialized_attempt(*, question: str, sql: str, key: str) -> dict[str, object]:
    return {
        "attempt_id": ATTEMPT_ID,
        "session_id": "privacy-session",
        "chat_session_id": CHAT_SESSION_ID,
        "user_id": USER_ID,
        "database_connection_id": str(CONNECTION_ID),
        "question": _encrypted_text(question, "attempt.question", key),
        "sql": _encrypted_text(sql, "attempt.sql", key),
        "attempt_number": 1,
        "state": "PENDING",
        "llm_provider": "",
        "evaluator_result": None,
        "created_at": "",
        "expires_at": "",
    }


@pytest.mark.parametrize(
    "corruption",
    [
        "legacy_plaintext",
        "tampered",
        "wrong_key",
        "unsupported_version",
        "wrong_purpose",
        "malformed",
        "malformed_document",
    ],
)
async def test_corrupt_attempt_state_fails_closed_and_is_deleted(corruption: str, test_encryption_key: str) -> None:
    """Corrupt or legacy text cannot be used as a valid attempt."""
    stored = _serialized_attempt(question="question", sql="SELECT 1", key=test_encryption_key)
    if corruption == "legacy_plaintext":
        stored["question"] = "legacy plaintext"
    elif corruption == "tampered":
        ciphertext = bytearray(base64.b64decode(stored["question"]))
        ciphertext[-1] ^= 1
        stored["question"] = base64.b64encode(ciphertext).decode()
    elif corruption == "wrong_key":
        wrong_key = base64.b64encode(b"wrong-key-32-bytes-for-test!!!!!").decode()
        stored["question"] = _encrypted_text("question", "attempt.question", wrong_key)
    elif corruption == "unsupported_version":
        stored["question"] = _encrypted_text("question", "attempt.question", test_encryption_key, version=2)
    elif corruption == "wrong_purpose":
        stored["question"] = _encrypted_text("question", "attempt.sql", test_encryption_key)
    elif corruption == "malformed":
        stored["question"] = "not-a-ciphertext"

    redis = AsyncMock(spec=Redis)
    redis_value = "not-json" if corruption == "malformed_document" else json.dumps(stored)
    redis.get = AsyncMock(return_value=redis_value)
    redis.eval = AsyncMock(return_value=1)

    with pytest.raises(AttemptContextInvalid) as exc_info:
        await get_attempt(ATTEMPT_ID, "privacy-session", USER_ID, redis)

    sanitized_error = str(exc_info.value) == str(AttemptContextInvalid())
    assert sanitized_error is True, "corrupt attempt returned a non-constant error"
    expected_cleanup_count = 0 if corruption == "malformed_document" else 1
    assert redis.eval.await_count == expected_cleanup_count
    redis.delete.assert_not_called()


@pytest.mark.parametrize(
    "evaluator_document",
    [
        pytest.param({}, id="missing-fields"),
        pytest.param({"passed": "false", "violations": []}, id="passed-string"),
        pytest.param({"passed": True, "violations": []}, id="passed-true"),
        pytest.param({"passed": False, "violations": {}}, id="violations-object"),
        pytest.param({"passed": False, "violations": [{}]}, id="violation-missing-fields"),
        pytest.param(
            {"passed": False, "violations": [{"rule": ["nested"], "message_key": "error.invalid"}]},
            id="nested-rule",
        ),
        pytest.param(
            {"passed": False, "violations": [{"rule": "rule", "message_key": "error.invalid", "extra": 1}]},
            id="unknown-violation-field",
        ),
    ],
)
async def test_invalid_evaluator_structure_is_rejected_before_use(
    evaluator_document,
    test_encryption_key: str,
) -> None:
    stored = _serialized_attempt(question="question", sql="SELECT 1", key=test_encryption_key)
    stored["state"] = "REJECTED"
    stored["evaluator_result"] = _encrypted_text(
        json.dumps(evaluator_document),
        "attempt.evaluator_result",
        test_encryption_key,
    )
    redis = AsyncMock(spec=Redis)
    redis.get = AsyncMock(return_value=json.dumps(stored))
    redis.eval = AsyncMock(return_value=1)

    with pytest.raises(AttemptContextInvalid):
        await get_attempt(ATTEMPT_ID, "privacy-session", USER_ID, redis)

    redis.eval.assert_awaited_once()


async def test_attempt_text_round_trip_uses_authenticated_markers_and_fresh_nonces(test_encryption_key: str) -> None:
    """Question and SQL restore in memory without plaintext Redis bytes."""
    redis = AsyncMock(spec=Redis)
    redis.set = AsyncMock(return_value=True)
    canary = "chunk28-round-trip-canary"
    attempt = EphemeralAttempt(
        attempt_id=ATTEMPT_ID,
        session_id="privacy-session",
        chat_session_id=CHAT_SESSION_ID,
        user_id=USER_ID,
        database_connection_id=CONNECTION_ID,
        question=canary,
        sql=f"SELECT '{canary}'",
    )

    await store_attempt(attempt, attempt.session_id, redis)
    first_serialized = redis.set.await_args.args[1]
    await store_attempt(attempt, attempt.session_id, redis)
    second_serialized = redis.set.await_args.args[1]

    first = json.loads(first_serialized)
    second = json.loads(second_serialized)
    ciphertexts_differ = first["question"] != second["question"]
    first_payload = json.loads(decrypt(first["question"], test_encryption_key))
    markers_valid = first_payload == {"purpose": "attempt.question", "version": 1, "text": canary}
    plaintext_absent = canary not in first_serialized and canary.encode() not in base64.b64decode(first["question"])
    assert ciphertexts_differ is True, "attempt encryption reused a nonce"
    assert markers_valid is True, "attempt text marker validation is incorrect"
    assert plaintext_absent is True, "attempt ciphertext exposes the canary"

    redis.get = AsyncMock(return_value=first_serialized)
    restored = await get_attempt(ATTEMPT_ID, "privacy-session", USER_ID, redis)
    question_restored = restored.question == canary
    sql_restored = restored.sql == f"SELECT '{canary}'"
    assert question_restored is True, "question could not be restored for retry"
    assert sql_restored is True, "generated SQL could not be restored for retry"


async def test_evaluator_payload_round_trips_only_after_authenticated_decryption(test_encryption_key: str) -> None:
    """Sealed evaluator metadata remains available to server-side consumers."""
    redis = AsyncMock(spec=Redis)
    redis.set = AsyncMock(return_value=True)
    canary = "chunk28-evaluator-round-trip-canary"
    evaluator_result = {"passed": False, "violations": [{"rule": canary, "message_key": canary}]}
    attempt = EphemeralAttempt(
        attempt_id=ATTEMPT_ID,
        session_id="privacy-session",
        chat_session_id=CHAT_SESSION_ID,
        user_id=USER_ID,
        database_connection_id=CONNECTION_ID,
        question="question",
        state="REJECTED",
        evaluator_result=evaluator_result,
    )

    await store_attempt(attempt, attempt.session_id, redis)
    serialized = redis.set.await_args.args[1]
    redis.get = AsyncMock(return_value=serialized)
    restored = await get_attempt(ATTEMPT_ID, "privacy-session", USER_ID, redis)

    metadata_restored = restored.evaluator_result == evaluator_result
    canary_absent = canary not in serialized
    assert metadata_restored is True, "sealed evaluator metadata could not be restored"
    assert canary_absent is True, "evaluator metadata was serialized as plaintext"


async def test_evaluator_payload_cannot_retain_user_canary() -> None:
    """Evaluator metadata is not a plaintext escape hatch for user input."""
    redis = AsyncMock(spec=Redis)
    redis.set = AsyncMock(return_value=True)
    canary = "chunk28-evaluator-canary"
    attempt = EphemeralAttempt(
        attempt_id=ATTEMPT_ID,
        session_id="privacy-session",
        chat_session_id=CHAT_SESSION_ID,
        user_id=USER_ID,
        database_connection_id=CONNECTION_ID,
        question="question",
        state="REJECTED",
        evaluator_result={"passed": False, "violations": [{"rule": canary, "message_key": canary}]},
    )

    await store_attempt(attempt, attempt.session_id, redis)

    serialized = redis.set.await_args.args[1]
    canary_present = canary in serialized
    assert canary_present is False, "serialized evaluator metadata contains user input"
