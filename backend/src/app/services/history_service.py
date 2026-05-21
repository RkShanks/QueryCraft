"""HistoryService — list and detail queries for accepted_queries."""

import uuid
from typing import Any

from fastapi import HTTPException, status

from app.core.exceptions import InvalidCursorError
from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.history import AcceptedQueryDetail, HistoryListResponse
from app.schemas.query import AcceptedQuerySummary


class HistoryService:
    """Read-only history operations."""

    def __init__(self, repository: AcceptedQueryRepository, connection_repository: ConnectionRepository | None = None):
        self._repo = repository
        self._connection_repo = connection_repository

    async def _connection_metadata(self, connection_id: Any) -> dict[str, str | None]:
        if not connection_id or self._connection_repo is None:
            return {"database_connection_name": None, "database_type": None}
        conn = await self._connection_repo.get_by_id(uuid.UUID(str(connection_id)))
        if conn is None:
            return {"database_connection_name": None, "database_type": None}
        database_type = getattr(conn.database_type, "value", conn.database_type)
        return {
            "database_connection_name": conn.display_name,
            "database_type": database_type,
        }

    async def list_history(self, user_id: str, cursor: str | None = None, limit: int = 100) -> HistoryListResponse:
        """Return paginated accepted queries."""
        from uuid import UUID

        try:
            items, next_cursor = await self._repo.list_by_user(UUID(user_id), cursor=cursor, limit=limit)
        except InvalidCursorError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "invalid_cursor", "message_key": "error.invalidCursor"},
            ) from None
        summaries = []
        for q in items:
            metadata = await self._connection_metadata(q.database_connection_id)
            summaries.append(
                AcceptedQuerySummary(
                    id=str(q.id),
                    question_text=q.question_text,
                    generated_sql=q.generated_sql,
                    accepted_at=q.accepted_at.isoformat(),
                    database_connection_id=(str(q.database_connection_id) if q.database_connection_id else None),
                    database_connection_name=metadata["database_connection_name"],
                    database_type=metadata["database_type"],
                )
            )
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

        metadata = await self._connection_metadata(query.database_connection_id)
        return AcceptedQueryDetail(
            id=str(query.id),
            question_text=query.question_text,
            generated_sql=query.generated_sql,
            llm_provider=query.llm_provider,
            accepted_at=query.accepted_at.isoformat(),
            database_connection_id=str(query.database_connection_id) if query.database_connection_id else None,
            database_connection_name=metadata["database_connection_name"],
            database_type=metadata["database_type"],
            result_columns=query.result_columns,
            result_rows=query.result_rows,
            result_row_count=query.result_row_count,
        )

    async def delete_entry(self, query_id: uuid.UUID, user_id: str) -> bool:
        """Delete a single accepted query entry. Returns True if deleted, False if not found."""
        from uuid import UUID

        return await self._repo.delete_by_id(query_id, UUID(user_id))
