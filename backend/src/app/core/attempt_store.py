"""Ephemeral attempt storage in Redis.

T-110: store_attempt, get_attempt, delete_attempt with session ownership
validation (Inv 6) and 15-minute TTL.
"""

import binascii
import json
import uuid
from typing import Any, Literal

from cryptography.exceptions import InvalidTag
from pydantic import BaseModel, ConfigDict, ValidationError
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


class _EncryptedAttemptText(BaseModel):
    """Authenticated payload for user-controlled attempt text."""

    purpose: Literal["attempt.question", "attempt.sql"]
    version: Literal[1]
    text: str


_QUESTION_PURPOSE = "attempt.question"
_SQL_PURPOSE = "attempt.sql"


# Default TTL from settings; can be overridden in tests.
_ATTEMPT_TTL_SECONDS = 15 * 60


def _seal_attempt_text(text: str, purpose: str) -> str:
    payload = _EncryptedAttemptText(purpose=purpose, version=1, text=text)
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


async def store_attempt(
    attempt: EphemeralAttempt,
    session_id: str,
    redis: Redis,
    ttl: int = _ATTEMPT_TTL_SECONDS,
) -> None:
    """Serialize *attempt* to JSON and store in Redis with TTL."""
    data = attempt.model_dump(mode="json")
    # Ensure session_id is present for ownership validation
    data["session_id"] = session_id
    data["question"] = _seal_attempt_text(attempt.question, _QUESTION_PURPOSE)
    data["sql"] = _seal_attempt_text(attempt.sql, _SQL_PURPOSE)
    key = f"attempt:{data.get('attempt_id')}"
    await redis.set(key, json.dumps(data), ex=ttl)


async def get_attempt(
    attempt_id: str,
    session_id: str,
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
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        await redis.delete(key)
        raise AttemptContextInvalid from None
    if not isinstance(data, dict):
        await redis.delete(key)
        raise AttemptContextInvalid()
    stored_session = data.get("session_id")
    if stored_session != session_id:
        raise AttemptOwnershipViolation()

    try:
        data["question"] = _open_attempt_text(data.get("question"), _QUESTION_PURPOSE)
        data["sql"] = _open_attempt_text(data.get("sql"), _SQL_PURPOSE)
        return EphemeralAttempt.model_validate(data)
    except (AttemptContextInvalid, ValidationError):
        await redis.delete(key)
        raise AttemptContextInvalid from None


async def delete_attempt(attempt_id: str, redis: Redis) -> None:
    """Remove an attempt from Redis."""
    key = f"attempt:{attempt_id}"
    await redis.delete(key)
