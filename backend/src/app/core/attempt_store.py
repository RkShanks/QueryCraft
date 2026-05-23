"""Ephemeral attempt storage in Redis.

T-110: store_attempt, get_attempt, delete_attempt with session ownership
validation (Inv 6) and 15-minute TTL.
"""

import datetime
import json
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from redis.asyncio import Redis

from app.core.exceptions import AttemptNotFound, AttemptOwnershipViolation


class _DecimalEncoder(json.JSONEncoder):
    """JSON encoder that converts Decimal to float and datetime/date/time to ISO string."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return obj.isoformat()
        return super().default(obj)


class EphemeralAttempt(BaseModel):
    """An attempt stored temporarily in Redis."""

    attempt_id: str
    session_id: str
    user_id: str = ""
    sql: str = ""
    question: str = ""
    attempt_number: int = 1
    state: str = "PENDING"  # PENDING | GENERATED | EVALUATED | EXECUTED | REJECTED | TIMEOUT
    llm_provider: str = ""
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
    await redis.set(key, json.dumps(data, cls=_DecimalEncoder), ex=ttl)


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
