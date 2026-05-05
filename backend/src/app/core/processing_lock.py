"""Redis processing lock primitives.

T-108: Implements acquire_lock and release_lock using SET NX EX.
"""

from redis.asyncio import Redis


async def acquire_lock(session_id: str, redis: Redis, ttl: int = 60) -> bool:
    """Try to acquire a per-session processing lock.

    Returns True if the lock was acquired, False if it is already held.
    """
    key = f"processing_lock:{session_id}"
    result = await redis.set(key, "1", nx=True, ex=ttl)
    return result is not None


async def release_lock(session_id: str, redis: Redis) -> None:
    """Release the per-session processing lock."""
    key = f"processing_lock:{session_id}"
    await redis.delete(key)
