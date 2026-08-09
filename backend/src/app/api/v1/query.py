"""Query router — submit, accept, reject, regenerate."""

import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.permissions import require_permission
from app.api.dependencies.validation import validate_body
from app.core.attempt_store import get_attempt
from app.core.config import get_settings
from app.core.dependencies import get_db, get_redis, require_active_user
from app.core.exceptions import AttemptContextInvalid, AttemptNotFound, AttemptOwnershipViolation, SessionBusy
from app.core.session_cancellation import ensure_session_active
from app.db.models.enums import Permission
from app.evaluator.pipeline import Evaluator
from app.evaluator.rules.dialect_validation import DialectValidationRule
from app.evaluator.rules.empty_sql import EmptySqlRule
from app.evaluator.rules.read_only import DIALECT_MAP, ReadOnlyRule
from app.evaluator.rules.schema_validation import SchemaValidationRule
from app.evaluator.rules.single_statement import SingleStatementRule
from app.evaluator.rules.unsafe_pattern import UnsafePatternRule
from app.llm.factory import LLMProviderFactory
from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.repositories.connection_repository import ConnectionRepository
from app.repositories.quota_repository import QuotaRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.query import (
    AcceptQueryRequest,
    EvaluatorRejection,
    QueryLimitsResponse,
    QueryResult,
    RefinePrompt,
    RegenerateQueryRequest,
    RejectQueryRequest,
    SubmitQuestionRequest,
)
from app.services.query_service import QueryService
from app.services.quota_service import QuotaService
from app.services.role_policy_provider import make_role_policy_provider
from app.source_db.connector import SourceDBConnector
from app.source_db.executor import SourceDBExecutor

router = APIRouter(prefix="/query", tags=["Query"])

# Module-level connector + executor (lives for app lifetime)
_source_db_connector = SourceDBConnector()
_source_db_executor = SourceDBExecutor(_source_db_connector)


@dataclass(frozen=True)
class AttemptServiceContext:
    """Authenticated identity and ownership keys for a query decision."""

    attempt_id: str
    http_session_id: str
    user_id: str


async def close_source_db_connector() -> None:
    """Release the module-level source connection pool."""
    await _source_db_connector.aclose()


async def _build_query_service_for_connection(
    connection_id: str,
    db: AsyncSession,
    redis: Redis,
) -> QueryService:
    """Build QueryService scoped to a specific connection (T-433).

    Validates connection is active + healthy + introspected.
    Uses connection-specific schema and dialect.
    """
    try:
        conn_uuid = uuid.UUID(connection_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "connection_not_found", "message_key": "error.connection_not_found"},
        ) from exc

    conn_repo = ConnectionRepository(db)
    conn = await conn_repo.get_by_id(conn_uuid)
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "connection_not_found", "message_key": "error.connection_not_found"},
        )

    from app.db.models.enums import HealthStatus, LifecycleState, SchemaIntrospectionStatus

    if conn.lifecycle_state != LifecycleState.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "connection_disabled", "message_key": "error.connection_disabled"},
        )
    if conn.health_status != HealthStatus.HEALTHY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "connection_unhealthy", "message_key": "error.connection_unhealthy"},
        )
    if conn.schema_introspection_status != SchemaIntrospectionStatus.SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "connection_no_schema", "message_key": "error.connection_no_schema"},
        )

    # Get connection-specific schema
    schema_entries = await conn_repo.get_schema_entries(conn.id)
    from app.evaluator.schema_context import Column, SchemaContext, Table

    tables = {}
    for entry in schema_entries:
        if entry.table_name not in tables:
            tables[entry.table_name] = Table(name=entry.table_name, columns=[])
        tables[entry.table_name].columns.append(
            Column(
                name=entry.column_name,
                data_type=entry.column_data_type,
                is_primary_key=entry.is_primary_key,
            )
        )

    schema_context = SchemaContext(tables=list(tables.values()))

    # Get dialect from connection type
    dialect = DIALECT_MAP.get(conn.database_type, "postgres")

    # Build connection-specific adapter
    from app.core.credential_provider import FernetCredentialProvider
    from app.db.models.enums import DatabaseType
    from app.source_db.adapters import MSSQLAdapter, MySQLAdapter, PostgresAdapter

    settings = get_settings()
    credential_provider = FernetCredentialProvider(settings.DB_CREDENTIAL_KEY)

    adapter_map = {
        DatabaseType.POSTGRESQL: PostgresAdapter,
        DatabaseType.MYSQL: MySQLAdapter,
        DatabaseType.MSSQL: MSSQLAdapter,
    }
    adapter_cls = adapter_map.get(conn.database_type)
    if adapter_cls is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "unsupported_dialect", "message_key": "error.unsupported_dialect"},
        )

    adapter = adapter_cls(
        host=conn.host,
        port=conn.port,
        database=conn.database_name,
        username=conn.username,
        encrypted_password=conn.encrypted_password,
        ssl_mode=conn.ssl_mode,
        credential_provider=credential_provider,
    )

    quota_repo = QuotaRepository(db)
    quota_service = QuotaService(redis=redis, quota_repo=quota_repo)
    return QueryService(
        accepted_query_repository=AcceptedQueryRepository(db),
        session_repository=SessionRepository(db),
        db_session=db,
        redis=redis,
        llm=LLMProviderFactory.from_config(settings),
        evaluator=Evaluator(
            rules=[
                EmptySqlRule(),
                DialectValidationRule(dialect=dialect),
                ReadOnlyRule(dialect=dialect),
                SingleStatementRule(dialect=dialect),
                SchemaValidationRule(schema_context, dialect=dialect),
                UnsafePatternRule(dialect=dialect),
            ]
        ),
        source_db_executor=_source_db_executor,
        llm_provider=settings.LLM_PROVIDER,
        schema_context=schema_context,
        target_dialect=dialect,
        connection_id=connection_id,
        source_db_adapter=adapter,
        role_policy_provider=make_role_policy_provider(db),
        quota_service=quota_service,
        query_timeout_seconds=settings.QUERY_TIMEOUT_SECONDS,
    )


async def _build_query_service_for_attempt(
    context: AttemptServiceContext,
    db: AsyncSession,
    redis: Redis,
) -> QueryService:
    """Build a service from immutable, server-owned attempt context."""
    active_attempt_id = await redis.get(f"active_attempt:{context.http_session_id}")
    if active_attempt_id != context.attempt_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "attempt_not_active", "message_key": "error.attemptInvalid"},
        )

    attempt = await get_attempt(context.attempt_id, context.http_session_id, redis)
    if attempt.user_id != context.user_id:
        raise AttemptOwnershipViolation()
    if attempt.chat_session_id is None:
        raise AttemptContextInvalid()
    await ensure_session_active(attempt.chat_session_id, redis)

    user_uuid = uuid.UUID(context.user_id)
    existing = await AcceptedQueryRepository(db).get_by_attempt_id(context.attempt_id, user_uuid)
    if existing is not None and existing.database_connection_id != attempt.database_connection_id:
        raise AttemptContextInvalid()

    service = await _build_query_service_for_connection(str(attempt.database_connection_id), db, redis)
    await service.ensure_connection_authorized(context.user_id)
    return service


@router.get("/limits", response_model=QueryLimitsResponse)
async def get_query_limits(
    _session: dict = Depends(require_permission(Permission.QUERY_SUBMIT)),  # noqa: B008
) -> QueryLimitsResponse:
    """Return the configured question limit for authorized submitters."""
    return QueryLimitsResponse(
        max_question_length=get_settings().MAX_QUESTION_LENGTH,
    )


@router.post("/submit")
async def submit_question(
    request: Request,
    _session: dict = Depends(require_permission(Permission.QUERY_SUBMIT)),  # noqa: B008
    req: SubmitQuestionRequest = Depends(validate_body(SubmitQuestionRequest)),  # noqa: B008
    user_id: str = Depends(require_active_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
):
    """POST /query/submit — ask a question.

    Requires ``query.submit`` permission.

    Response shapes:
    - 200 → QueryResult (returned directly)
    - 422 → EvaluatorRejection (raised as HTTPException, unwrapped by global handler)
    response_model is intentionally omitted because the endpoint returns
    discriminated union shapes; openapi.yaml remains the source of truth.
    """
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
    service = await _build_query_service_for_connection(req.connection_id, db, redis)
    result = await service.submit_question(
        http_session_id=request.state.session_id,
        user_id=user_id,
        question=stripped,
        chat_session_id=req.session_id,
        connection_id=req.connection_id,
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
    _session: dict = Depends(require_permission(Permission.QUERY_SUBMIT)),  # noqa: B008
    req: AcceptQueryRequest = Depends(validate_body(AcceptQueryRequest)),  # noqa: B008
    user_id: str = Depends(require_active_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
):
    """POST /query/accept — persist the current result.

    Requires ``query.submit`` permission.

    The service is rebuilt from immutable connection context in the Redis attempt.
    """
    try:
        context = AttemptServiceContext(req.attempt_id, request.state.session_id, user_id)
        service = await _build_query_service_for_attempt(
            context,
            db,
            redis,
        )
        return await service.accept_query(
            http_session_id=request.state.session_id,
            user_id=user_id,
            attempt_id=req.attempt_id,
            chat_session_id=req.session_id,
        )
    except AttemptNotFound:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "attempt_expired", "message_key": "error.attemptExpired"},
        ) from None
    except (AttemptContextInvalid, AttemptOwnershipViolation):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "attempt_invalid", "message_key": "error.attemptInvalid"},
        ) from None


@router.post("/reject", response_model=QueryResult | RefinePrompt)
async def reject_query(
    request: Request,
    _session: dict = Depends(require_permission(Permission.QUERY_SUBMIT)),  # noqa: B008
    req: RejectQueryRequest = Depends(validate_body(RejectQueryRequest)),  # noqa: B008
    user_id: str = Depends(require_active_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
):
    """POST /query/reject — reject current result and trigger auto-retry.

    Requires ``query.submit`` permission.
    """
    try:
        context = AttemptServiceContext(req.attempt_id, request.state.session_id, user_id)
        service = await _build_query_service_for_attempt(
            context,
            db,
            redis,
        )
        return await service.reject_query(
            attempt_id=req.attempt_id,
            http_session_id=request.state.session_id,
            user_id=user_id,
        )
    except AttemptNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "attempt_invalid", "message_key": exc.message_key},
        ) from exc
    except (AttemptContextInvalid, AttemptOwnershipViolation):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "attempt_invalid", "message_key": "error.attemptInvalid"},
        ) from None
    except SessionBusy as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "concurrent", "message_key": exc.message_key},
        ) from exc


@router.post("/regenerate", response_model=QueryResult | RefinePrompt)
async def regenerate_query(
    request: Request,
    _session: dict = Depends(require_permission(Permission.QUERY_SUBMIT)),  # noqa: B008
    req: RegenerateQueryRequest = Depends(validate_body(RegenerateQueryRequest)),  # noqa: B008
    user_id: str = Depends(require_active_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
):
    """POST /query/regenerate — regenerate SQL with negative context.

    Requires ``query.submit`` permission.
    """
    try:
        context = AttemptServiceContext(req.attempt_id, request.state.session_id, user_id)
        service = await _build_query_service_for_attempt(
            context,
            db,
            redis,
        )
        return await service.regenerate_query(
            attempt_id=req.attempt_id,
            http_session_id=request.state.session_id,
            user_id=user_id,
        )
    except AttemptNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "attempt_invalid", "message_key": exc.message_key},
        ) from exc
    except (AttemptContextInvalid, AttemptOwnershipViolation):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "attempt_invalid", "message_key": "error.attemptInvalid"},
        ) from None
    except SessionBusy as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "concurrent", "message_key": exc.message_key},
        ) from exc
