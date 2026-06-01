"""SessionRepository — data access for sessions table."""

import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.session import Session


class SessionRepository:
    """Repository for chat sessions."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, user_id: uuid.UUID, preview_text: str = "") -> Session:
        """Create a new session."""
        session = Session(user_id=user_id, preview_text=preview_text)
        self._session.add(session)
        await self._session.flush()
        await self._session.refresh(session)
        return session

    async def list_by_user(self, user_id: uuid.UUID) -> list[Session]:
        """Return sessions for a user, reverse-chronological by last_activity."""
        result = await self._session.execute(
            select(Session).where(Session.user_id == user_id).order_by(desc(Session.last_activity_at))
        )
        return list(result.scalars().all())

    async def get_by_id(self, session_id: uuid.UUID, user_id: uuid.UUID) -> Session | None:
        """Fetch a single session by ID and user."""
        result = await self._session.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete(self, session_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a session (cascade deletes accepted_queries). Returns True if deleted."""
        result = await self._session.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            return False
        await self._session.delete(session)
        await self._session.flush()
        return True

    async def update_last_activity(self, session_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Update last_activity_at to now()."""
        result = await self._session.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            return False
        session.last_activity_at = datetime.now(UTC)
        await self._session.flush()
        return True

    async def update_preview_text(self, session_id: uuid.UUID, user_id: uuid.UUID, preview_text: str) -> bool:
        """Update preview text (truncated to 60 chars + ellipsis)."""
        result = await self._session.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            return False
        truncated = preview_text if len(preview_text) <= 60 else preview_text[:60] + "..."
        session.preview_text = truncated
        await self._session.flush()
        return True

    async def update_connection(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        connection_id: uuid.UUID,
    ) -> Session | None:
        """Update session's selected connection (T-434, FR-094)."""
        result = await self._session.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            return None
        session.connection_id = connection_id
        session.last_activity_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(session)
        return session

    # ------------------------------------------------------------------
    # Concurrent session limit enforcement (FR-127, S-010)
    # ------------------------------------------------------------------

    @staticmethod
    async def enforce_concurrent_session_limit(
        redis: Redis,
        user_id: str,
        new_session_id: str,
        created_at: float,
        max_sessions: int,
        session_ttl_seconds: int,
    ) -> None:
        """Add new session to user index and evict oldest if over limit.

        Uses a Redis sorted set keyed by user_id with score = created_at timestamp.
        Oldest sessions (lowest score) are evicted first when count exceeds
        ``max_sessions``.  A limit <= 0 disables enforcement.

        This is a static helper so both AuthService and SsoService can share
        the same eviction logic without duplicating code.
        """
        # Guard against mocked / missing settings values in tests
        try:
            max_sessions = int(max_sessions)
        except Exception:
            max_sessions = 5
        if max_sessions <= 0:
            return

        user_index_key = f"user_sessions:{user_id}"

        # Add new session to sorted set (score = creation time)
        await redis.zadd(user_index_key, {new_session_id: created_at})
        # Refresh TTL on index to match session TTL
        await redis.expire(user_index_key, session_ttl_seconds)

        # Count current sessions for this user
        current_count = await redis.zcard(user_index_key)
        overflow = int(current_count) - max_sessions
        if overflow > 0:
            # Fetch oldest overflow session IDs before removing
            oldest_ids = await redis.zrange(user_index_key, 0, overflow - 1)
            if oldest_ids:
                for sid in oldest_ids:
                    await redis.delete(f"session:{sid}")
                await redis.zrem(user_index_key, *oldest_ids)
