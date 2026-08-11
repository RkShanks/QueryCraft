"""AcceptedQueryRepository — data access for accepted_queries table."""

import uuid
from datetime import datetime

from sqlalchemy import and_, desc, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidCursorError
from app.core.pagination import decode_cursor, encode_cursor
from app.db.models.accepted_query import AcceptedQuery

_ATTEMPT_CURSOR_NAMESPACE = "session_attempts"


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
        attempt_id: str | None = None,
        session_id: uuid.UUID | None = None,
        saved: bool = False,
        feedback: int | None = None,
        result_columns: list | None = None,
        result_rows: list | None = None,
        result_row_count: int | None = None,
    ) -> AcceptedQuery:
        """Persist a new accepted query."""
        query = AcceptedQuery(
            user_id=user_id,
            database_connection_id=database_connection_id,
            question_text=question_text,
            generated_sql=generated_sql,
            llm_provider=llm_provider,
            attempt_id=attempt_id,
            session_id=session_id,
            saved=saved,
            feedback=feedback,
            result_columns=result_columns,
            result_rows=result_rows,
            result_row_count=result_row_count,
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
            # Decode composite cursor as "accepted_at|id"
            from datetime import datetime

            try:
                parts = cursor.split("|")
                if len(parts) != 2:
                    raise ValueError("Invalid cursor format")
                cursor_dt = datetime.fromisoformat(parts[0])
                cursor_id = uuid.UUID(parts[1])
                stmt = stmt.where(tuple_(AcceptedQuery.accepted_at, AcceptedQuery.id) < tuple_(cursor_dt, cursor_id))
            except ValueError:
                raise InvalidCursorError() from None

        result = await self._session.execute(stmt)
        items = list(result.scalars().all())

        next_cursor = None
        if len(items) > limit:
            items = items[:limit]
            next_cursor = f"{items[-1].accepted_at.isoformat()}|{items[-1].id}"

        return items, next_cursor

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        """Return total number of accepted queries for a user."""
        result = await self._session.execute(
            select(func.count()).select_from(AcceptedQuery).where(AcceptedQuery.user_id == user_id)
        )
        return result.scalar_one() or 0

    async def get_by_id(self, query_id: uuid.UUID, user_id: uuid.UUID) -> AcceptedQuery | None:
        """Fetch a single accepted query by ID and user."""
        result = await self._session.execute(
            select(AcceptedQuery).where(
                AcceptedQuery.id == query_id,
                AcceptedQuery.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_session(self, session_id: uuid.UUID, user_id: uuid.UUID, limit: int = 100) -> list[AcceptedQuery]:
        """Return completed accepted queries for a session, reverse-chronological.

        Skips pending attempts — only accepted or rejected attempts count.
        """
        result = await self._session.execute(
            select(AcceptedQuery)
            .where(
                AcceptedQuery.session_id == session_id,
                AcceptedQuery.user_id == user_id,
            )
            .order_by(desc(AcceptedQuery.accepted_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def page_by_session(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[AcceptedQuery], str | None]:
        """Return one stable, ownership-scoped attempt page."""
        statement = (
            select(AcceptedQuery)
            .where(AcceptedQuery.session_id == session_id, AcceptedQuery.user_id == user_id)
            .order_by(desc(AcceptedQuery.accepted_at), desc(AcceptedQuery.id))
            .limit(limit + 1)
        )
        if cursor is not None:
            position = decode_cursor(cursor, _ATTEMPT_CURSOR_NAMESPACE)
            try:
                accepted_at = datetime.fromisoformat(position.sort_value)
                if accepted_at.tzinfo is None:
                    raise ValueError
            except ValueError:
                raise InvalidCursorError() from None
            statement = statement.where(
                or_(
                    AcceptedQuery.accepted_at < accepted_at,
                    and_(AcceptedQuery.accepted_at == accepted_at, AcceptedQuery.id < position.item_id),
                )
            )

        rows = list((await self._session.execute(statement)).scalars().all())
        if len(rows) <= limit:
            return rows, None
        page = rows[:limit]
        last = page[-1]
        return page, encode_cursor(_ATTEMPT_CURSOR_NAMESPACE, last.accepted_at.isoformat(), last.id)

    async def count_by_session(self, session_id: uuid.UUID, user_id: uuid.UUID) -> int:
        """Return the exact ownership-scoped attempt total."""
        statement = (
            select(func.count())
            .select_from(AcceptedQuery)
            .where(AcceptedQuery.session_id == session_id, AcceptedQuery.user_id == user_id)
        )
        return int((await self._session.execute(statement)).scalar_one())

    async def update_feedback(
        self, query_id: uuid.UUID, user_id: uuid.UUID, feedback: int, saved: bool | None = None
    ) -> AcceptedQuery | None:
        """Update feedback on an accepted query. Returns updated row or None.

        When feedback=1 and saved is not explicitly passed, saved defaults to True.
        Pass saved=False to explicitly opt out.
        """
        result = await self._session.execute(
            select(AcceptedQuery).where(
                AcceptedQuery.id == query_id,
                AcceptedQuery.user_id == user_id,
            )
        )
        query = result.scalar_one_or_none()
        if query is None:
            return None
        query.feedback = feedback
        if saved is not None:
            query.saved = saved
        elif feedback == 1:
            query.saved = True
        await self._session.flush()
        return query

    async def get_latest_by_session(self, session_id: uuid.UUID, user_id: uuid.UUID) -> AcceptedQuery | None:
        """Return the most recent accepted query in a session."""
        result = await self._session.execute(
            select(AcceptedQuery)
            .where(
                AcceptedQuery.session_id == session_id,
                AcceptedQuery.user_id == user_id,
            )
            .order_by(desc(AcceptedQuery.accepted_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def delete_by_id(self, query_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a single accepted query row by ID and user. Returns True if deleted."""
        result = await self._session.execute(
            select(AcceptedQuery).where(
                AcceptedQuery.id == query_id,
                AcceptedQuery.user_id == user_id,
            )
        )
        query = result.scalar_one_or_none()
        if query is None:
            return False
        await self._session.delete(query)
        await self._session.flush()
        return True

    async def get_by_attempt_id(self, attempt_id: str, user_id: uuid.UUID) -> AcceptedQuery | None:
        """Fetch an existing accepted query by ephemeral attempt_id (for idempotency)."""
        result = await self._session.execute(
            select(AcceptedQuery).where(
                AcceptedQuery.attempt_id == attempt_id,
                AcceptedQuery.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
