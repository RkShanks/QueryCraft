"""History router — list and detail."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.schemas.history import HistoryListResponse
from app.services.history_service import HistoryService

router = APIRouter(prefix="/history", tags=["History"])


def _get_history_service(db: AsyncSession = Depends(get_db)) -> HistoryService:  # noqa: B008
    return HistoryService(AcceptedQueryRepository(db))


@router.get("", response_model=HistoryListResponse)
async def list_history(
    request: Request,
    cursor: str | None = None,
    limit: int = 100,
    service: HistoryService = Depends(_get_history_service),  # noqa: B008
):
    """GET /history — list accepted queries."""
    session = request.state.session
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    return await service.list_history(
        user_id=session["user_id"],
        cursor=cursor,
        limit=limit,
    )


@router.get("/{query_id}")
async def get_history_entry(
    request: Request,
    query_id: str,
    service: HistoryService = Depends(_get_history_service),  # noqa: B008
):
    """GET /history/{id} — single accepted query detail."""
    session = request.state.session
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    return await service.get_detail(query_id, session["user_id"])
