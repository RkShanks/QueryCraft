"""HistoryService — list and detail queries for accepted_queries."""

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidCursorError
from app.db.models.enums import AuditActionType
from app.repositories.accepted_query_repository import (
    AcceptedQueryRepository,
    search_cursor_namespace,
)
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.history import AcceptedQueryDetail, HistoryListResponse
from app.schemas.query import AcceptedQuerySummary
from app.services.audit_service import AuditService

HISTORY_SEARCH_MAX_CODE_POINTS = 200


def normalize_history_search(raw: str | None) -> str | None:
    """Return the trimmed bounded history search, or None when unfiltered.

    Whitespace-only input means unfiltered history. The trimmed value must
    not exceed ``HISTORY_SEARCH_MAX_CODE_POINTS`` Unicode code points.
    """
    if raw is None:
        return None
    normalized = raw.strip()
    if not normalized:
        return None
    if "\x00" in normalized or len(normalized) > HISTORY_SEARCH_MAX_CODE_POINTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_search", "message_key": "error.invalidSearch"},
        )
    return normalized


__all__ = [
    "HISTORY_SEARCH_MAX_CODE_POINTS",
    "HistoryService",
    "normalize_history_search",
    "search_cursor_namespace",
]


class HistoryService:
    """Read-only history operations."""

    def __init__(
        self,
        repository: AcceptedQueryRepository,
        connection_repository: ConnectionRepository | None = None,
        db_session: AsyncSession | None = None,
    ):
        self._repo = repository
        self._connection_repo = connection_repository
        self._db_session = db_session

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

    async def list_history(
        self,
        user_id: str,
        cursor: str | None = None,
        limit: int = 100,
        actor_identity: str | None = None,
        search: str | None = None,
    ) -> HistoryListResponse:
        """Return paginated accepted queries, optionally search-filtered."""
        from uuid import UUID

        normalized_search = normalize_history_search(search)

        try:
            items, next_cursor = await self._repo.list_by_user(
                UUID(user_id), cursor=cursor, limit=limit, search=normalized_search
            )
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
            total = await self._repo.count_by_user(UUID(user_id), search=normalized_search)
        if self._db_session is not None:
            context: dict[str, Any] = {"operation": "list"}
            # Record only that filtering happened — never the raw search text.
            if normalized_search is not None:
                context["searched"] = True
            await AuditService.log(
                self._db_session,
                action=AuditActionType.QUERY_HISTORY_VIEW,
                actor_id=UUID(user_id),
                actor_identity=actor_identity,
                resource_type="accepted_query_history",
                resource_id=None,
                outcome="success",
                context=context,
            )
        return HistoryListResponse(items=summaries, total=total, next_cursor=next_cursor)

    async def get_detail(
        self,
        query_id: uuid.UUID,
        user_id: str,
        actor_identity: str | None = None,
    ) -> AcceptedQueryDetail:
        """Return a single accepted query detail."""
        from uuid import UUID

        query = await self._repo.get_by_id(query_id, UUID(user_id))
        if query is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message_key": "error.notFound"},
            )

        metadata = await self._connection_metadata(query.database_connection_id)
        detail = AcceptedQueryDetail(
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
        if self._db_session is not None:
            await AuditService.log(
                self._db_session,
                action=AuditActionType.QUERY_HISTORY_VIEW,
                actor_id=UUID(user_id),
                actor_identity=actor_identity,
                resource_type="accepted_query",
                resource_id=str(query.id),
                outcome="success",
                context={"operation": "detail"},
            )
        return detail

    async def delete_entry(self, query_id: uuid.UUID, user_id: str) -> bool:
        """Delete a single accepted query entry. Returns True if deleted, False if not found."""
        from uuid import UUID

        return await self._repo.delete_by_id(query_id, UUID(user_id))
