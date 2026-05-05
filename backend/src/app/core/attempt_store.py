"""Ephemeral attempt storage in Redis.

T-110: store_attempt, get_attempt, delete_attempt with session ownership
validation (Inv 6) and 15-minute TTL.
"""

import json
from typing import Any

from pydantic import BaseModel
from redis.asyncio import Redis

from app.core.exceptions import AttemptExpired, AttemptNotFound, AttemptOwnershipViolation


class EphemeralAttempt(BaseModel):
    """An attempt stored temporarily in Redis."""

    attempt_id: str
    session_id: str
    sql: str
    question: str = ""
    attempt_number: int = 1
    evaluator_result: dict[str, Any] | None = None
    executor_result: dict[str, Any] | None = None
    created_at: str = ""
    expires_at: str = ""


# Default TTL from settings; can be overridden in tests.
_ATTEMPT_TTL_SECONDS = 15 * 60


async def store_attempt(
    attempt: BaseModel,
    session_id: str,
    redis: Redis,
    ttl: int = _ATTEMPT_TTL_SECONDS,
) -> None:
    """Serialize *attempt* to JSON and store in Redis with TTL."""
    data = attempt.model_dump() if hasattr(attempt, "model_dump") else attempt.dict()
    # Ensure session_id is present for ownership validation
    data["session_id"] = session_id
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

    data = json.loads(raw)
    stored_session = data.get("session_id")
    if stored_session != session_id:
        raise AttemptOwnershipViolation()

    return EphemeralAttempt(**data)


async def delete_attempt(attempt_id: str, redis: Redis) -> None:
    """Remove an attempt from Redis."""
    key = f"attempt:{attempt_id}"
    await redis.delete(key)
