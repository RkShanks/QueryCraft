"""Sessions router — CRUD for chat sessions."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_active_user
from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.session import (
    CreateSessionResponse,
    SessionDetail,
    SessionListResponse,
    SessionSummary,
)

router = APIRouter(prefix="/sessions", tags=["Sessions"])


def _get_session_repo(db: AsyncSession = Depends(get_db)) -> SessionRepository:  # noqa: B008
    return SessionRepository(db)


def _get_accepted_query_repo(db: AsyncSession = Depends(get_db)) -> AcceptedQueryRepository:  # noqa: B008
    return AcceptedQueryRepository(db)


@router.post("", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: Request,
    repo: SessionRepository = Depends(_get_session_repo),  # noqa: B008
    user_id: str = Depends(require_active_user),  # noqa: B008
):
    """POST /sessions — create a new session."""
    new_session = await repo.create(
        user_id=uuid.UUID(user_id),
    )
    return CreateSessionResponse(
        id=str(new_session.id),
        preview_text=new_session.preview_text,
        created_at=new_session.created_at.isoformat(),
    )


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    request: Request,
    repo: SessionRepository = Depends(_get_session_repo),  # noqa: B008
    user_id: str = Depends(require_active_user),  # noqa: B008
):
    """GET /sessions — list sessions for the current user."""
    items = await repo.list_by_user(uuid.UUID(user_id))
    return SessionListResponse(
        items=[
            SessionSummary(
                id=str(s.id),
                preview_text=s.preview_text,
                created_at=s.created_at.isoformat(),
                last_activity_at=s.last_activity_at.isoformat(),
            )
            for s in items
        ],
        total=len(items),
    )


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    request: Request,
    session_id: uuid.UUID,
    session_repo: SessionRepository = Depends(_get_session_repo),  # noqa: B008
    query_repo: AcceptedQueryRepository = Depends(_get_accepted_query_repo),  # noqa: B008
    user_id: str = Depends(require_active_user),  # noqa: B008
):
    """GET /sessions/:id — get session detail with conversation history."""
    user_uuid = uuid.UUID(user_id)
    sess = await session_repo.get_by_id(session_id, user_uuid)
    if sess is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        )
    attempts = await query_repo.list_by_session(session_id, user_uuid)
    return SessionDetail(
        id=str(sess.id),
        preview_text=sess.preview_text,
        created_at=sess.created_at.isoformat(),
        last_activity_at=sess.last_activity_at.isoformat(),
        attempts=[
            {
                "id": str(a.id),
                "question_text": a.question_text,
                "generated_sql": a.generated_sql,
                "accepted_at": a.accepted_at.isoformat(),
                "saved": a.saved,
                "feedback": a.feedback,
                "result_columns": a.result_columns,
                "result_rows": a.result_rows,
                "result_row_count": a.result_row_count,
            }
            for a in attempts
        ],
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    request: Request,
    session_id: uuid.UUID,
    repo: SessionRepository = Depends(_get_session_repo),  # noqa: B008
    user_id: str = Depends(require_active_user),  # noqa: B008
):
    """DELETE /sessions/:id — delete a session (cascade deletes accepted_queries)."""
    deleted = await repo.delete(session_id, uuid.UUID(user_id))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        )
