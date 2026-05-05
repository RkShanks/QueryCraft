"""AcceptedQueryRepository — data access for accepted_queries table."""

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.accepted_query import AcceptedQuery


class AcceptedQueryRepository:
    """Repository for accepted (persisted) queries."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self,
        user_id: uuid.UUID,
        database_connection_id: uuid.UUID,
        question_text: str,
        generated_sql: str,
        llm_provider: str,
    ) -> AcceptedQuery:
        """Persist a new accepted query."""
        query = AcceptedQuery(
            user_id=user_id,
            database_connection_id=database_connection_id,
            question_text=question_text,
            generated_sql=generated_sql,
            llm_provider=llm_provider,
        )
        self._session.add(query)
        await self._session.flush()
        await self._session.refresh(query)
        return query

    async def list_by_user(
        self, user_id: uuid.UUID, cursor: str | None = None, limit: int = 100
    ) -> tuple[list[AcceptedQuery], str | None]:
        """Return accepted queries for a user, reverse-chronological, with cursor pagination."""
        stmt = (
            select(AcceptedQuery)
            .where(AcceptedQuery.user_id == user_id)
            .order_by(desc(AcceptedQuery.accepted_at), desc(AcceptedQuery.id))
            .limit(limit + 1)
        )
        if cursor:
            # Decode cursor as ISO timestamp string and filter
            from datetime import datetime

            try:
                cursor_dt = datetime.fromisoformat(cursor)
                stmt = stmt.where(AcceptedQuery.accepted_at < cursor_dt)
            except ValueError:
                pass

        result = await self._session.execute(stmt)
        items = list(result.scalars().all())

        next_cursor = None
        if len(items) > limit:
            items = items[:limit]
            next_cursor = items[-1].accepted_at.isoformat()

        return items, next_cursor

    async def get_by_id(self, query_id: uuid.UUID, user_id: uuid.UUID) -> AcceptedQuery | None:
        """Fetch a single accepted query by ID and user."""
        result = await self._session.execute(
            select(AcceptedQuery).where(
                AcceptedQuery.id == query_id,
                AcceptedQuery.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
