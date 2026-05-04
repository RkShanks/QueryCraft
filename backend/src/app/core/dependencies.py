"""FastAPI dependency injection wiring."""

from collections.abc import AsyncGenerator

from fastapi import Request
from redis.asyncio import Redis

from app.core.config import get_settings
from app.db.base import get_db as _get_db  # noqa: F401 — re-exported

# Re-export get_db for convenience
get_db = _get_db

_redis_client: Redis | None = None


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency: yields an async Redis client."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    yield _redis_client


async def init_redis() -> Redis:
    """Initialize and verify Redis connection (for lifespan)."""
    global _redis_client
    settings = get_settings()
    _redis_client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )
    await _redis_client.ping()
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection (for shutdown)."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


async def get_current_user(request: Request) -> dict:
    """Read session from request state and return user info, or raise 401.

    This is a stub that reads session data set by the session middleware.
    """
    from fastapi import HTTPException, status

    session_data = getattr(request.state, "session", None)
    if session_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    return session_data
