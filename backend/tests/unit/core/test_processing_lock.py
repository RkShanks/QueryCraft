"""T-107: Redis processing lock tests.

Tests that acquire_lock returns True on first call, False on concurrent,
that release_lock deletes the key, and that the key format is correct.
"""

from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis

from app.core.processing_lock import acquire_lock, release_lock


class TestProcessingLockUnit:
    """Unit tests for processing lock using mocked redis."""

    async def test_acquire_lock_returns_true_when_free(self):
        """Acquiring lock when free returns True."""
        redis = AsyncMock(spec=Redis)
        redis.set = AsyncMock(return_value=True)
        result = await acquire_lock("session-123", redis, ttl=60)
        assert result is True
        redis.set.assert_awaited_once_with("processing_lock:session-123", "1", nx=True, ex=60)

    async def test_acquire_lock_returns_false_when_held(self):
        """Acquiring lock when already held returns False."""
        redis = AsyncMock(spec=Redis)
        redis.set = AsyncMock(return_value=None)
        result = await acquire_lock("session-123", redis, ttl=60)
        assert result is False

    async def test_release_lock_deletes_key(self):
        """release_lock deletes the lock key."""
        redis = AsyncMock(spec=Redis)
        redis.delete = AsyncMock()
        await release_lock("session-123", redis)
        redis.delete.assert_awaited_once_with("processing_lock:session-123")

    async def test_lock_key_format(self):
        """Lock key follows expected format."""
        redis = AsyncMock(spec=Redis)
        redis.set = AsyncMock(return_value=True)
        await acquire_lock("session-abc", redis, ttl=60)
        call_args = redis.set.call_args
        assert call_args.kwargs["nx"] is True
        assert call_args.kwargs["ex"] == 60
        assert call_args.args[0] == "processing_lock:session-abc"


@pytest.mark.integration
class TestProcessingLockIntegration:
    """Integration tests with real redis fixture."""

    async def test_acquire_with_real_redis(self, redis_client):
        """Acquire and release with testcontainers redis."""
        result = await acquire_lock("sess-1", redis_client, ttl=10)
        assert result is True
        result2 = await acquire_lock("sess-1", redis_client, ttl=10)
        assert result2 is False
        await release_lock("sess-1", redis_client)
        result3 = await acquire_lock("sess-1", redis_client, ttl=10)
        assert result3 is True
