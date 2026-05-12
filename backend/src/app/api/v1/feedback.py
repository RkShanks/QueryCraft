"""Feedback router — update feedback on accepted queries."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.schemas.feedback import FeedbackResponse, UpdateFeedbackRequest

router = APIRouter(prefix="/feedback", tags=["Feedback"])


def _get_repo(db: AsyncSession = Depends(get_db)) -> AcceptedQueryRepository:  # noqa: B008
    return AcceptedQueryRepository(db)


@router.patch("/{attempt_id}", response_model=FeedbackResponse)
async def update_feedback(
    request: Request,
    attempt_id: uuid.UUID,
    req: UpdateFeedbackRequest,
    repo: AcceptedQueryRepository = Depends(_get_repo),  # noqa: B008
):
    """PATCH /feedback/:attempt_id — update feedback on an accepted query."""
    session = request.state.session
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    updated = await repo.update_feedback(
        attempt_id,
        uuid.UUID(session["user_id"]),
        req.feedback,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        )
    return FeedbackResponse(
        id=str(updated.id),
        feedback=updated.feedback,
        saved=updated.saved,
    )
