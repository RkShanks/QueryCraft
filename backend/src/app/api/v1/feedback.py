"""Feedback router — update feedback on accepted queries."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_active_user
from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.schemas.feedback import FeedbackResponse, UpdateFeedbackRequest

router = APIRouter(prefix="/feedback", tags=["Feedback"])


def _get_repo(db: AsyncSession = Depends(get_db)) -> AcceptedQueryRepository:  # noqa: B008
    return AcceptedQueryRepository(db)


@router.patch("/{attempt_id}", response_model=FeedbackResponse)
async def update_feedback(
    attempt_id: uuid.UUID,
    req: UpdateFeedbackRequest,
    user_id: str = Depends(require_active_user),  # noqa: B008
    repo: AcceptedQueryRepository = Depends(_get_repo),  # noqa: B008
):
    """PATCH /feedback/:attempt_id — update feedback on an accepted query."""
    updated = await repo.update_feedback(
        attempt_id,
        uuid.UUID(user_id),
        req.feedback,
        saved=req.saved,
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
