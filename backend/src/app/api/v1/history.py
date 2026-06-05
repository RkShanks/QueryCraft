"""History router — list and detail.

Per FR-134 / SC-053 and api-contracts.md line 359-362, every
endpoint in this module filters by ``user_id = current_user.id``
at the database query layer. There is no global / cross-user
visibility: an admin session sees only its own user_id's rows,
not a system-wide view. The chain is::

    request.state.session["user_id"]
        -> require_active_user (verifies DB user still exists)
        -> current_user_id endpoint parameter
        -> service.list_history / get_detail / delete_entry
        -> AcceptedQueryRepository.{list_by_user, count_by_user,
                                     get_by_id, delete_by_id}
        -> SQL ``WHERE accepted_queries.user_id = :user_id``

The ``current_user_id`` alias on each handler is intentional: it
mirrors the spec formula ``user_id = current_user.id`` at the
endpoint signature so a future reviewer can see the contract
without having to walk the dependency chain.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    _session: dict = Depends(require_permission(Permission.QUERY_HISTORY_VIEW)),  # noqa: B008
    current_user_id: str = Depends(require_active_user),  # noqa: B008
    service: HistoryService = Depends(_get_history_service),  # noqa: B008
):
    """GET /history — list accepted queries for the caller.

    Requires ``query.history.view`` permission. Filters by
    ``user_id = current_user.id`` (FR-134 / SC-053).
    """
    return await service.list_history(
        user_id=current_user_id,
        cursor=cursor,
        limit=limit,
    )


@router.get("/{query_id}")
async def get_history_entry(
    query_id: uuid.UUID,
    _session: dict = Depends(require_permission(Permission.QUERY_HISTORY_VIEW)),  # noqa: B008
    current_user_id: str = Depends(require_active_user),  # noqa: B008
    service: HistoryService = Depends(_get_history_service),  # noqa: B008
):
    """GET /history/{id} — single accepted query detail.

    Requires ``query.history.view`` permission. Filters by
    ``user_id = current_user.id`` (FR-134 / SC-053); a query
    belonging to another user returns 404.
    """
    return await service.get_detail(query_id, current_user_id)


@router.delete("/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_entry(
    query_id: uuid.UUID,
    _session: dict = Depends(require_permission(Permission.QUERY_HISTORY_VIEW)),  # noqa: B008
    current_user_id: str = Depends(require_active_user),  # noqa: B008
    service: HistoryService = Depends(_get_history_service),  # noqa: B008
):
    """DELETE /history/{id} — delete a single saved query result.

    Requires ``query.history.view`` permission. Filters by
    ``user_id = current_user.id`` (FR-134 / SC-053); a query
    belonging to another user returns 404.
    """
    deleted = await service.delete_entry(query_id, current_user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        )
