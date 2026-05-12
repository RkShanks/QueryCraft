"""SessionRepository — data access for sessions table."""

import uuid
from datetime import datetime

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
        session.last_activity_at = datetime.now(datetime.timezone.utc)
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
