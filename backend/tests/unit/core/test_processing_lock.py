"""T-107: Redis processing lock tests.

Tests that acquire_lock returns owner token on first call, None on concurrent,
that release_lock deletes the key, and that release_lock_if_owned is safe.
"""

from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis

from app.core.processing_lock import acquire_lock, release_lock, release_lock_if_owned


class TestProcessingLockUnit:
    """Unit tests for processing lock using mocked redis."""

    async def test_acquire_lock_returns_owner_when_free(self):
        """Acquiring lock when free returns an owner token string."""
        redis = AsyncMock(spec=Redis)
        redis.set = AsyncMock(return_value="owner-123")
        result = await acquire_lock("session-123", redis, ttl=60)
        assert result is not None
        assert isinstance(result, str)

    async def test_acquire_lock_returns_none_when_held(self):
        """Acquiring lock when already held returns None."""
        redis = AsyncMock(spec=Redis)
        redis.set = AsyncMock(return_value=None)
        result = await acquire_lock("session-123", redis, ttl=60)
        assert result is None

    async def test_release_lock_deletes_key(self):
        """release_lock deletes the lock key."""
        redis = AsyncMock(spec=Redis)
        redis.delete = AsyncMock()
        await release_lock("session-123", redis)
        redis.delete.assert_awaited_once_with("processing_lock:session-123")

    async def test_lock_key_format_with_owner(self):
        """Lock key uses owner token as value."""
        redis = AsyncMock(spec=Redis)
        redis.set = AsyncMock(return_value="owner-abc")
        await acquire_lock("session-abc", redis, ttl=60)
        call_args = redis.set.call_args
        assert call_args.kwargs["nx"] is True
        assert call_args.kwargs["ex"] == 60
        assert call_args.args[0] == "processing_lock:session-abc"
        # Value should be a uuid string (not just "1")
        assert len(call_args.args[1]) == 36  # uuid4 hex format

    async def test_release_lock_if_owned_matching_owner(self):
        """release_lock_if_owned deletes when owner matches."""
        redis = AsyncMock(spec=Redis)
        redis.eval = AsyncMock(return_value=1)
        result = await release_lock_if_owned("session-123", "owner-123", redis)
        assert result is True

    async def test_release_lock_if_owned_wrong_owner(self):
        """release_lock_if_owned does nothing when owner doesn't match."""
        redis = AsyncMock(spec=Redis)
        redis.eval = AsyncMock(return_value=0)
        result = await release_lock_if_owned("session-123", "wrong-owner", redis)
        assert result is False

    async def test_release_lock_if_owned_none_owner(self):
        """release_lock_if_owned with None owner returns False."""
        redis = AsyncMock(spec=Redis)
        result = await release_lock_if_owned("session-123", None, redis)
        assert result is False


@pytest.mark.integration
class TestProcessingLockIntegration:
    """Integration tests with real redis fixture."""

    async def test_acquire_with_real_redis(self, redis_client):
        """Acquire and release with testcontainers redis."""
        result = await acquire_lock("sess-1", redis_client, ttl=10)
        assert result is not None
        assert isinstance(result, str)
        result2 = await acquire_lock("sess-1", redis_client, ttl=10)
        assert result2 is None
        await release_lock("sess-1", redis_client)
        result3 = await acquire_lock("sess-1", redis_client, ttl=10)
        assert result3 is not None

    async def test_release_lock_if_owned_with_real_redis(self, redis_client):
        """release_lock_if_owned with real redis."""
        owner = await acquire_lock("sess-2", redis_client, ttl=10)
        assert owner is not None
        # Correct owner releases the lock
        released = await release_lock_if_owned("sess-2", owner, redis_client)
        assert released is True
        # Now lock is free
        new_owner = await acquire_lock("sess-2", redis_client, ttl=10)
        assert new_owner is not None
        # Wrong owner does not release
        not_released = await release_lock_if_owned("sess-2", "wrong-owner", redis_client)
        assert not_released is False
        # Only correct owner releases
        correct_release = await release_lock_if_owned("sess-2", new_owner, redis_client)
        assert correct_release is True
