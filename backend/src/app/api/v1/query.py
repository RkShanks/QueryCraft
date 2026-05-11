"""Query router — submit, accept, reject, regenerate."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.validation import validate_body
from app.core.config import get_settings
from app.core.dependencies import get_db, get_redis
from app.core.exceptions import AttemptNotFound, AttemptOwnershipViolation, SessionBusy
from app.evaluator.pipeline import Evaluator
from app.evaluator.rules.read_only import ReadOnlyRule
from app.evaluator.rules.schema_validation import SchemaValidationRule
from app.evaluator.rules.single_statement import SingleStatementRule
from app.evaluator.rules.unsafe_pattern import UnsafePatternRule
from app.llm.factory import LLMProviderFactory
from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.schemas.query import (
    AcceptQueryRequest,
    EvaluatorRejection,
    QueryResult,
    RefinePrompt,
    RegenerateQueryRequest,
    RejectQueryRequest,
    SubmitQuestionRequest,
)
from app.services.query_service import QueryService
from app.source_db.connector import SourceDBConnector
from app.source_db.executor import SourceDBExecutor
from app.source_db.introspector import SchemaIntrospector

router = APIRouter(prefix="/query", tags=["Query"])

# Module-level connector + executor + introspector (lives for app lifetime)
_source_db_connector = SourceDBConnector()
_source_db_executor = SourceDBExecutor(_source_db_connector)
_source_introspector = SchemaIntrospector(_source_db_connector)


async def _get_query_service(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
) -> QueryService:
    schema_context = await _source_introspector.introspect()
    settings = get_settings()
    return QueryService(
        accepted_query_repository=AcceptedQueryRepository(db),
        redis=redis,
        llm=LLMProviderFactory.from_config(settings),
        evaluator=Evaluator(
            rules=[
                ReadOnlyRule(),
                SingleStatementRule(),
                SchemaValidationRule(schema_context),
                UnsafePatternRule(),
            ]
        ),
        source_db_executor=_source_db_executor,
        llm_provider=settings.LLM_PROVIDER,
        schema_context=schema_context,
    )


@router.post("/submit")
async def submit_question(
    request: Request,
    req: SubmitQuestionRequest = Depends(validate_body(SubmitQuestionRequest)),  # noqa: B008
    service: QueryService = Depends(_get_query_service),  # noqa: B008
):
    """POST /query/submit — ask a question.

    Response shapes:
    - 200 → QueryResult (returned directly)
    - 422 → EvaluatorRejection (raised as HTTPException, unwrapped by global handler)
    response_model is intentionally omitted because the endpoint returns
    discriminated union shapes; openapi.yaml remains the source of truth.
    """
    session = request.state.session
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
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
    result = await service.submit_question(
        session_id=request.state.session_id,
        user_id=session["user_id"],
        question=stripped,
    )
    if isinstance(result, EvaluatorRejection):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.model_dump(),
        )
    return result


@router.post("/accept", status_code=status.HTTP_201_CREATED)
async def accept_query(
    request: Request,
    req: AcceptQueryRequest = Depends(validate_body(AcceptQueryRequest)),  # noqa: B008
    service: QueryService = Depends(_get_query_service),  # noqa: B008
):
    """POST /query/accept — persist the current result."""
    session = request.state.session
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    attempt_id = req.attempt_id
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
        attempt_id=attempt_id,
        database_connection_id=db_id,
    )


@router.post("/reject", response_model=QueryResult | RefinePrompt)
async def reject_query(
    request: Request,
    req: RejectQueryRequest = Depends(validate_body(RejectQueryRequest)),  # noqa: B008
    service: QueryService = Depends(_get_query_service),  # noqa: B008
):
    """POST /query/reject — reject current result and trigger auto-retry."""
    session = request.state.session
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    try:
        return await service.reject_query(
            attempt_id=req.attempt_id,
            session_id=request.state.session_id,
        )
    except (AttemptNotFound, AttemptOwnershipViolation) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "attempt_invalid", "message_key": exc.message_key},
        ) from exc
    except SessionBusy as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "concurrent", "message_key": exc.message_key},
        ) from exc


@router.post("/regenerate", response_model=QueryResult | RefinePrompt)
async def regenerate_query(
    request: Request,
    req: RegenerateQueryRequest = Depends(validate_body(RegenerateQueryRequest)),  # noqa: B008
    service: QueryService = Depends(_get_query_service),  # noqa: B008
):
    """POST /query/regenerate — regenerate SQL with negative context."""
    session = request.state.session
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    try:
        return await service.regenerate_query(
            attempt_id=req.attempt_id,
            session_id=request.state.session_id,
        )
    except (AttemptNotFound, AttemptOwnershipViolation) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "attempt_invalid", "message_key": exc.message_key},
        ) from exc
    except SessionBusy as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "concurrent", "message_key": exc.message_key},
        ) from exc
