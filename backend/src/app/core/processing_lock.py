"""Redis processing lock primitives.

T-108: Implements acquire_lock and release_lock using SET NX EX.
"""

from redis.asyncio import Redis


async def acquire_lock(session_id: str, redis: Redis, ttl: int = 60) -> str | None:
    """Try to acquire a per-session processing lock.

    Returns an owner token (uuid string) if acquired, None if already held.
    """
    import uuid

    key = f"processing_lock:{session_id}"
    owner = str(uuid.uuid4())
    result = await redis.set(key, owner, nx=True, ex=ttl)
    return owner if result is not None else None


async def release_lock(session_id: str, redis: Redis) -> None:
    """Release the per-session processing lock unconditionally."""
    key = f"processing_lock:{session_id}"
    await redis.delete(key)


async def release_lock_if_owned(session_id: str, owner: str | None, redis: Redis) -> bool:
    """Release the processing lock only if the stored owner token matches.

    Returns True if the lock was released, False if not owned or already released.
    This prevents an operation from deleting another operation's lock.
    """
    if owner is None:
        return False
    key = f"processing_lock:{session_id}"
    # Lua script for atomic compare-and-delete
    script = """
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
    end
    return 0
    """
    result = await redis.eval(script, 1, key, owner)
    return result == 1
