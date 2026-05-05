"""T-107: Redis processing lock tests.

Tests that acquire_lock returns True on first call, False on concurrent,
that release_lock deletes the key, and that the key format is correct.
"""

import pytest
from redis.asyncio import Redis

from app.core.processing_lock import acquire_lock, release_lock


class TestProcessingLockUnit:
    """Unit tests for processing lock using mocked redis."""

    async def test_acquire_lock_returns_true_when_free(self):
        """Acquiring lock when free returns True."""
        redis = Redis.from_url("redis://localhost:6379/1", decode_responses=True)
        await redis.flushdb()
        try:
            result = await acquire_lock("session-123", redis, ttl=60)
            assert result is True
        finally:
            await redis.flushdb()
            await redis.aclose()

    async def test_acquire_lock_returns_false_when_held(self):
        """Acquiring lock when already held returns False."""
        redis = Redis.from_url("redis://localhost:6379/1", decode_responses=True)
        await redis.flushdb()
        try:
            first = await acquire_lock("session-123", redis, ttl=60)
            assert first is True
            second = await acquire_lock("session-123", redis, ttl=60)
            assert second is False
        finally:
            await redis.flushdb()
            await redis.aclose()

    async def test_release_lock_deletes_key(self):
        """release_lock deletes the lock key."""
        redis = Redis.from_url("redis://localhost:6379/1", decode_responses=True)
        await redis.flushdb()
        try:
            await acquire_lock("session-123", redis, ttl=60)
            await release_lock("session-123", redis)
            # After release, lock should be acquirable again
            result = await acquire_lock("session-123", redis, ttl=60)
            assert result is True
        finally:
            await redis.flushdb()
            await redis.aclose()

    async def test_lock_key_format(self):
        """Lock key follows expected format."""
        redis = Redis.from_url("redis://localhost:6379/1", decode_responses=True)
        await redis.flushdb()
        try:
            await acquire_lock("session-abc", redis, ttl=60)
            keys = await redis.keys("processing_lock:*")
            assert len(keys) == 1
            assert keys[0] == "processing_lock:session-abc"
            ttl = await redis.ttl("processing_lock:session-abc")
            assert ttl > 0
        finally:
            await redis.flushdb()
            await redis.aclose()


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
