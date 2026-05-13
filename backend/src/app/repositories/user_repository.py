"""UserRepository — data access for users table."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


class UserRepository:
    """Repository for user lookups."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_username(self, username: str) -> User | None:
        """Fetch a user by exact username match."""
        result = await self._session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()
