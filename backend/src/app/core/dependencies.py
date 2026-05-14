"""FastAPI dependency injection wiring."""

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.base import get_db as _get_db  # noqa: F401 — re-exported
from app.db.models.user import User

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
    session_data = getattr(request.state, "session", None)
    if session_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    return session_data


async def require_active_user(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
) -> str:
    """Validate the Redis session user still exists in the database.

    Returns the user_id (string) if the user exists.
    If the user has been deleted, the stale Redis session is cleaned up
    and a 401 is raised.

    Use this dependency on any endpoint that creates or modifies data
    keyed by user_id to prevent FK violations on stale sessions.
    """
    session = getattr(request.state, "session", None)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    user_id = uuid.UUID(session["user_id"])
    result = await db.execute(select(User).where(User.id == user_id))
    if result.scalar_one_or_none() is None:
        session_id = getattr(request.state, "session_id", None)
        if session_id:
            await redis.delete(f"session:{session_id}")
            request.state.session = None
            request.state.session_id = None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    return session["user_id"]
