"""Query router — submit, accept, reject, regenerate."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.validation import validate_body
from app.core.config import get_settings
from app.core.dependencies import get_db, get_redis, require_active_user
from app.core.exceptions import AttemptNotFound, AttemptOwnershipViolation, SessionBusy
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
from app.repositories.session_repository import SessionRepository
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
        session_repository=SessionRepository(db),
        db_session=db,
        redis=redis,
        llm=LLMProviderFactory.from_config(settings),
        evaluator=Evaluator(
            rules=[
                EmptySqlRule(),
                ReadOnlyRule(),
                SingleStatementRule(),
                SchemaValidationRule(schema_context, dialect="postgres"),
                UnsafePatternRule(),
            ]
        ),
        source_db_executor=_source_db_executor,
        llm_provider=settings.LLM_PROVIDER,
        schema_context=schema_context,
    )


async def _build_query_service_for_connection(
    connection_id: str,
    db: AsyncSession,
    redis: Redis,
) -> QueryService:
    """Build QueryService scoped to a specific connection (T-433).

    Validates connection is active + healthy + introspected.
    Uses connection-specific schema and dialect.
    """
    conn_repo = ConnectionRepository(db)
    conn = await conn_repo.get_by_id(uuid.UUID(connection_id))
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
                SingleStatementRule(),
                SchemaValidationRule(schema_context, dialect=dialect),
                UnsafePatternRule(),
            ]
        ),
        source_db_executor=_source_db_executor,
        llm_provider=settings.LLM_PROVIDER,
        schema_context=schema_context,
        target_dialect=dialect,
        connection_id=connection_id,
        source_db_adapter=adapter,
    )


@router.post("/submit")
async def submit_question(
    request: Request,
    req: SubmitQuestionRequest = Depends(validate_body(SubmitQuestionRequest)),  # noqa: B008
    user_id: str = Depends(require_active_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
):
    """POST /query/submit — ask a question.

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
    req: AcceptQueryRequest = Depends(validate_body(AcceptQueryRequest)),  # noqa: B008
    user_id: str = Depends(require_active_user),  # noqa: B008
    service: QueryService = Depends(_get_query_service),  # noqa: B008
):
    """POST /query/accept — persist the current result.

    High 2: database_connection_id is now resolved inside QueryService.accept_query
    via _get_database_connection_id() on the same request-scoped DB session.
    """
    return await service.accept_query(
        http_session_id=request.state.session_id,
        user_id=user_id,
        attempt_id=req.attempt_id,
        chat_session_id=req.session_id,
    )


@router.post("/reject", response_model=QueryResult | RefinePrompt)
async def reject_query(
    request: Request,
    req: RejectQueryRequest = Depends(validate_body(RejectQueryRequest)),  # noqa: B008
    user_id: str = Depends(require_active_user),  # noqa: B008
    service: QueryService = Depends(_get_query_service),  # noqa: B008
):
    """POST /query/reject — reject current result and trigger auto-retry."""
    try:
        return await service.reject_query(
            attempt_id=req.attempt_id,
            http_session_id=request.state.session_id,
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
    user_id: str = Depends(require_active_user),  # noqa: B008
    service: QueryService = Depends(_get_query_service),  # noqa: B008
):
    """POST /query/regenerate — regenerate SQL with negative context."""
    try:
        return await service.regenerate_query(
            attempt_id=req.attempt_id,
            http_session_id=request.state.session_id,
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
