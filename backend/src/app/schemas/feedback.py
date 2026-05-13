"""Feedback Pydantic schemas."""

from pydantic import BaseModel, Field


class UpdateFeedbackRequest(BaseModel):
    """PATCH /feedback/:attempt_id request body."""

    feedback: int = Field(..., ge=-1, le=1)
    saved: bool | None = None


class FeedbackResponse(BaseModel):
    """Response after updating feedback."""

    id: str
    feedback: int
    saved: bool
