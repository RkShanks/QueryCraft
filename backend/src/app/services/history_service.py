"""HistoryService — list and detail queries for accepted_queries."""

import uuid

from fastapi import HTTPException, status

from app.core.exceptions import InvalidCursorError
from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.schemas.history import AcceptedQueryDetail, HistoryListResponse
from app.schemas.query import AcceptedQuerySummary


class HistoryService:
    """Read-only history operations."""

    def __init__(self, repository: AcceptedQueryRepository):
        self._repo = repository

    async def list_history(self, user_id: str, cursor: str | None = None, limit: int = 100) -> HistoryListResponse:
        """Return paginated accepted queries."""
        from uuid import UUID

        try:
            items, next_cursor = await self._repo.list_by_user(UUID(user_id), cursor=cursor, limit=limit)
        except InvalidCursorError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "invalid_cursor", "message_key": "error.invalidCursor"},
            )
        summaries = [
            AcceptedQuerySummary(
                id=str(q.id),
                question_text=q.question_text,
                generated_sql=q.generated_sql,
                accepted_at=q.accepted_at.isoformat(),
            )
            for q in items
        ]
        total = None
        if cursor is None:
            total = await self._repo.count_by_user(UUID(user_id))
        return HistoryListResponse(items=summaries, total=total, next_cursor=next_cursor)

    async def get_detail(self, query_id: uuid.UUID, user_id: str) -> AcceptedQueryDetail:
        """Return a single accepted query detail."""
        from uuid import UUID

        query = await self._repo.get_by_id(query_id, UUID(user_id))
        if query is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message_key": "error.notFound"},
            )

        return AcceptedQueryDetail(
            id=str(query.id),
            question_text=query.question_text,
            generated_sql=query.generated_sql,
            llm_provider=query.llm_provider,
            accepted_at=query.accepted_at.isoformat(),
            database_connection_id=str(query.database_connection_id),
        )
