"""Regression coverage for plaintext attempt retention (CHUNK-28)."""

import json
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from redis.asyncio import Redis

from app.core.attempt_store import EphemeralAttempt, store_attempt


CONNECTION_ID = UUID("550e8400-e29b-41d4-a716-446655440001")


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
    assert canary not in serialized
    assert canary.encode() not in json.dumps(serialized).encode()

