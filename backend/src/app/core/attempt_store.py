"""Ephemeral attempt storage in Redis.

T-110: store_attempt, get_attempt, delete_attempt with session ownership
validation (Inv 6) and 15-minute TTL.
"""

import binascii
import json
import uuid
from typing import Annotated, Any, Literal

from cryptography.exceptions import InvalidTag
from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, field_validator, model_validator
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.encryption import decrypt, encrypt
from app.core.exceptions import AttemptContextInvalid, AttemptNotFound, AttemptOwnershipViolation


class EphemeralAttempt(BaseModel):
    """An attempt stored temporarily in Redis."""

    model_config = ConfigDict(extra="forbid")

    attempt_id: str
    session_id: str
    chat_session_id: str | None = None
    user_id: str = ""
    database_connection_id: uuid.UUID
    sql: str = ""
    question: str = ""
    attempt_number: int = 1
    state: str = "PENDING"  # PENDING | GENERATED | EVALUATED | EXECUTED | REJECTED | TIMEOUT | FAILED
    llm_provider: str = ""
    evaluator_result: dict[str, Any] | None = None
    created_at: str = ""
    expires_at: str = ""


NonEmptyString = Annotated[str, Field(min_length=1)]
AttemptState = Literal["PENDING", "GENERATED", "EVALUATED", "EXECUTED", "REJECTED", "TIMEOUT", "FAILED"]


def _require_canonical_uuid(identifier: str) -> str:
    try:
        parsed_identifier = uuid.UUID(identifier)
    except ValueError:
        raise ValueError("identifier must be a UUID") from None
    if str(parsed_identifier) != identifier:
        raise ValueError("identifier must be canonical")
    return identifier


class _AttemptOwnership(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    session_id: NonEmptyString
    user_id: NonEmptyString

    @field_validator("user_id")
    @classmethod
    def canonical_user_id(cls, identifier: str) -> str:
        return _require_canonical_uuid(identifier)


class _StoredAttemptRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    attempt_id: NonEmptyString
    session_id: NonEmptyString
    chat_session_id: NonEmptyString | None
    user_id: NonEmptyString
    database_connection_id: NonEmptyString
    sql: str
    question: str
    attempt_number: Annotated[StrictInt, Field(ge=1)]
    state: AttemptState
    llm_provider: str
    evaluator_result: str | None
    created_at: str
    expires_at: str

    @field_validator("attempt_id", "user_id", "database_connection_id")
    @classmethod
    def canonical_required_uuid(cls, identifier: str) -> str:
        return _require_canonical_uuid(identifier)

    @field_validator("chat_session_id")
    @classmethod
    def canonical_optional_uuid(cls, identifier: str | None) -> str | None:
        return _require_canonical_uuid(identifier) if identifier is not None else None

    @model_validator(mode="after")
    def evaluator_matches_state(self) -> "_StoredAttemptRecord":
        evaluator_present = self.evaluator_result is not None
        if evaluator_present != (self.state == "REJECTED"):
            raise ValueError("evaluator result does not match attempt state")
        return self


class _EvaluatorViolation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    rule: NonEmptyString
    message_key: NonEmptyString


class _StoredEvaluatorResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    passed: Literal[False]
    violations: Annotated[list[_EvaluatorViolation], Field(min_length=1)]


class _EncryptedAttemptText(BaseModel):
    """Authenticated payload for user-controlled attempt text."""

    model_config = ConfigDict(extra="forbid", strict=True)

    purpose: Literal["attempt.question", "attempt.sql", "attempt.evaluator_result"]
    version: Literal[1]
    text: str


_QUESTION_PURPOSE = "attempt.question"
_SQL_PURPOSE = "attempt.sql"
_EVALUATOR_PURPOSE = "attempt.evaluator_result"


# Default TTL from settings; can be overridden in tests.
_ATTEMPT_TTL_SECONDS = 15 * 60

_DELETE_CORRUPT_ATTEMPT_LUA = """
local key_type = redis.call('TYPE', KEYS[1]).ok
if key_type ~= 'none' and key_type ~= 'string' then
  return redis.error_reply('invalid-attempt-key-type')
end
local current = redis.call('GET', KEYS[1])
if current == false or current ~= ARGV[1] then
  return 0
end
return redis.call('DEL', KEYS[1])
"""


def _seal_attempt_text(plaintext: str, purpose: str) -> str:
    payload = _EncryptedAttemptText(purpose=purpose, version=1, text=plaintext)
    return encrypt(payload.model_dump_json(), get_settings().PLATFORM_ENCRYPTION_KEY)


def _open_attempt_text(ciphertext: Any, purpose: str) -> str:
    try:
        plaintext = decrypt(ciphertext, get_settings().PLATFORM_ENCRYPTION_KEY)
        payload = _EncryptedAttemptText.model_validate_json(plaintext)
    except (
        binascii.Error,
        InvalidTag,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        TypeError,
        ValueError,
    ):
        raise AttemptContextInvalid from None
    if payload.purpose != purpose:
        raise AttemptContextInvalid()
    return payload.text


def _restore_attempt_fields(stored_record: _StoredAttemptRecord) -> EphemeralAttempt:
    parsed_document = stored_record.model_dump()
    parsed_document["question"] = _open_attempt_text(parsed_document.get("question"), _QUESTION_PURPOSE)
    parsed_document["sql"] = _open_attempt_text(parsed_document.get("sql"), _SQL_PURPOSE)
    if parsed_document.get("evaluator_result") is not None:
        evaluator_json = _open_attempt_text(parsed_document["evaluator_result"], _EVALUATOR_PURPOSE)
        evaluator_result = _StoredEvaluatorResult.model_validate_json(evaluator_json)
        parsed_document["evaluator_result"] = evaluator_result.model_dump()
    return EphemeralAttempt.model_validate(parsed_document)


async def _delete_corrupt_attempt(redis: Redis, key: str, expected_attempt_json: str) -> None:
    await redis.eval(_DELETE_CORRUPT_ATTEMPT_LUA, 1, key, expected_attempt_json)


async def store_attempt(
    attempt: EphemeralAttempt,
    session_id: str,
    redis: Redis,
    ttl: int = _ATTEMPT_TTL_SECONDS,
) -> None:
    """Serialize *attempt* to JSON and store in Redis with TTL."""
    serialized_attempt = attempt.model_dump(mode="json")
    # Ensure session_id is present for ownership validation
    serialized_attempt["session_id"] = session_id
    serialized_attempt["question"] = _seal_attempt_text(attempt.question, _QUESTION_PURPOSE)
    serialized_attempt["sql"] = _seal_attempt_text(attempt.sql, _SQL_PURPOSE)
    if attempt.evaluator_result is not None:
        evaluator_json = json.dumps(attempt.evaluator_result, separators=(",", ":"))
        serialized_attempt["evaluator_result"] = _seal_attempt_text(evaluator_json, _EVALUATOR_PURPOSE)
    key = f"attempt:{serialized_attempt.get('attempt_id')}"
    await redis.set(key, json.dumps(serialized_attempt), ex=ttl)


async def get_attempt(
    attempt_id: str,
    session_id: str,
    user_id: str,
    redis: Redis,
) -> EphemeralAttempt:
    """Retrieve an attempt from Redis and validate session ownership.

    Raises:
        AttemptNotFound: if the key does not exist.
        AttemptExpired: if the key has expired (handled by Redis, but we
            treat a missing key after existing as expired).
        AttemptOwnershipViolation: if the stored session_id doesn't match.
    """
    key = f"attempt:{attempt_id}"
    raw = await redis.get(key)
    if raw is None:
        raise AttemptNotFound()

    try:
        parsed_document = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        raise AttemptContextInvalid from None
    if not isinstance(parsed_document, dict):
        raise AttemptContextInvalid()
    try:
        ownership = _AttemptOwnership.model_validate(parsed_document)
    except ValidationError:
        raise AttemptContextInvalid from None
    if ownership.session_id != session_id or ownership.user_id != user_id:
        raise AttemptOwnershipViolation()

    try:
        stored_record = _StoredAttemptRecord.model_validate(parsed_document)
        if stored_record.attempt_id != attempt_id:
            raise AttemptContextInvalid()
        return _restore_attempt_fields(stored_record)
    except (AttemptContextInvalid, ValidationError, json.JSONDecodeError, TypeError):
        await _delete_corrupt_attempt(redis, key, raw)
        raise AttemptContextInvalid from None


async def delete_attempt(attempt_id: str, redis: Redis) -> None:
    """Remove an attempt from Redis."""
    key = f"attempt:{attempt_id}"
    await redis.delete(key)
