"""History router — list and detail."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.permissions import require_permission
from app.core.dependencies import get_db, require_active_user
from app.db.models.enums import Permission
from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.history import HistoryListResponse
from app.services.history_service import HistoryService

router = APIRouter(prefix="/history", tags=["History"])


def _get_history_service(db: AsyncSession = Depends(get_db)) -> HistoryService:  # noqa: B008
    return HistoryService(AcceptedQueryRepository(db), ConnectionRepository(db))


@router.get("", response_model=HistoryListResponse)
async def list_history(
    request: Request,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    user_id: str = Depends(require_active_user),  # noqa: B008
    service: HistoryService = Depends(_get_history_service),  # noqa: B008
):
    """GET /history — list accepted queries.

    Requires ``query.history.view`` permission.
    """
    await require_permission(Permission.QUERY_HISTORY_VIEW)(request)
    return await service.list_history(
        user_id=user_id,
        cursor=cursor,
        limit=limit,
    )


@router.get("/{query_id}")
async def get_history_entry(
    request: Request,
    query_id: uuid.UUID,
    user_id: str = Depends(require_active_user),  # noqa: B008
    service: HistoryService = Depends(_get_history_service),  # noqa: B008
):
    """GET /history/{id} — single accepted query detail.

    Requires ``query.history.view`` permission.
    """
    await require_permission(Permission.QUERY_HISTORY_VIEW)(request)
    return await service.get_detail(query_id, user_id)


@router.delete("/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_entry(
    request: Request,
    query_id: uuid.UUID,
    user_id: str = Depends(require_active_user),  # noqa: B008
    service: HistoryService = Depends(_get_history_service),  # noqa: B008
):
    """DELETE /history/{id} — delete a single saved query result.

    Requires ``query.history.view`` permission.
    """
    await require_permission(Permission.QUERY_HISTORY_VIEW)(request)
    deleted = await service.delete_entry(query_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        )
