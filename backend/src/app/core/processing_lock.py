"""Redis processing lock primitives.

T-108: Implements acquire_lock and release_lock using SET NX EX.
"""

from threading import Lock
from uuid import uuid4

from redis.asyncio import Redis

_inflight_owners: dict[tuple[int, str], str] = {}
_inflight_guard = Lock()


def _reserve_inflight_owner(redis: Redis, key: str, owner: str) -> bool:
    inflight_key = (id(redis), key)
    with _inflight_guard:
        if inflight_key in _inflight_owners:
            return False
        _inflight_owners[inflight_key] = owner
        return True


def _release_inflight_owner(redis: Redis, key: str, owner: str | None = None) -> None:
    inflight_key = (id(redis), key)
    with _inflight_guard:
        current_owner = _inflight_owners.get(inflight_key)
        if owner is None or current_owner == owner:
            _inflight_owners.pop(inflight_key, None)


async def acquire_lock(session_id: str, redis: Redis, ttl: int = 60) -> str | None:
    """Try to acquire a per-session processing lock.

    Returns an owner token (uuid string) if acquired, None if already held.
    """
    key = f"processing_lock:{session_id}"
    owner = str(uuid4())
    if not _reserve_inflight_owner(redis, key, owner):
        return None

    redis_acquired = False
    try:
        redis_acquired = await redis.set(key, owner, nx=True, ex=ttl) is not None
        return owner if redis_acquired else None
    finally:
        if not redis_acquired:
            _release_inflight_owner(redis, key, owner)


async def release_lock(session_id: str, redis: Redis) -> None:
    """Release the per-session processing lock unconditionally."""
    key = f"processing_lock:{session_id}"
    try:
        await redis.delete(key)
    finally:
        _release_inflight_owner(redis, key)


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
    try:
        result = await redis.eval(script, 1, key, owner)
        return result == 1
    finally:
        _release_inflight_owner(redis, key, owner)
