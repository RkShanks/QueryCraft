"""Query router — submit, accept, reject, regenerate."""

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_redis
from app.evaluator.pipeline import Evaluator
from app.llm.stub import StubLLM
from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.schemas.query import AcceptQueryRequest, QueryResult, SubmitQuestionRequest
from app.services.query_service import QueryService
from app.source_db.executor import SourceDBExecutor

router = APIRouter(prefix="/query", tags=["Query"])


def _get_query_service(db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)) -> QueryService:
    return QueryService(
        accepted_query_repository=AcceptedQueryRepository(db),
        redis=redis,
        llm=StubLLM(),
        evaluator=Evaluator(),
        source_db_executor=SourceDBExecutor(),
    )


@router.post("/submit", response_model=QueryResult)
async def submit_question(
    request: Request,
    payload: dict = Body(...),
    service: QueryService = Depends(_get_query_service),
):
    """POST /query/submit — ask a question."""
    session = request.state.session
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    try:
        req = SubmitQuestionRequest.model_validate(payload)
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation", "message_key": "error.validation.generic"},
        )
    stripped = req.question.strip()
    if not stripped:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation", "message_key": "error.validation.questionEmpty"},
        )
    if len(stripped) > 2000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation", "message_key": "error.validation.questionTooLong"},
        )
    return await service.submit_question(
        session_id=request.state.session_id,
        user_id=session["user_id"],
        question=stripped,
    )


@router.post("/accept", status_code=status.HTTP_201_CREATED)
async def accept_query(
    request: Request,
    payload: AcceptQueryRequest,
    service: QueryService = Depends(_get_query_service),
):
    """POST /query/accept — persist the current result."""
    session = request.state.session
    if session is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    # Use the first database_connection as the target (Phase 1 has exactly one)
    from sqlalchemy import text
    from app.db.base import get_async_session_factory

    factory = get_async_session_factory()
    async with factory() as db:
        result = await db.execute(text("SELECT id FROM database_connections LIMIT 1"))
        row = result.fetchone()
        db_id = str(row[0]) if row else "00000000-0000-0000-0000-000000000000"

    return await service.accept_query(
        session_id=request.state.session_id,
        user_id=session["user_id"],
        attempt_id=payload.attempt_id,
        database_connection_id=db_id,
    )


@router.post("/reject")
async def reject_query():
    """POST /query/reject — stub for US-2."""
    return {"message": "stub"}


@router.post("/regenerate")
async def regenerate_query():
    """POST /query/regenerate — stub for US-2."""
    return {"message": "stub"}
