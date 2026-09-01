"""QueryService — submit, accept, reject, regenerate logic.

T-712: Policy enforcement integration. When a ``role_policy_provider``
is configured, the query flow becomes:

1. Resolve the user's role policy for the requested connection.
2. If the policy exists with an empty ``allowed_tables`` (deny-all),
   fail closed before the LLM with ``error.queryBlockedPolicy``.
3. Filter the schema using ``PolicyEnforcementService.filter_schema()``
   so the LLM prompt only sees role-allowed tables and columns.
4. Build a fresh evaluator that augments the existing evaluator's
   pipeline with a ``RoleAuthorizationRule`` using the role's
   ``allowed_tables``. The new rule runs after the existing rules
   and before execution.
5. After the existing evaluator passes, apply
   ``PolicyEnforcementService.apply_row_filters()`` to inject any
   per-role row filters via driver-style parameter placeholders.
   Execute using the rewritten SQL and the bound params tuple —
   user values are never interpolated.
6. After execution, apply
   ``PolicyEnforcementService.apply_column_masks()`` to the
   ``QueryResult`` so masked columns are replaced with ``"***"`` and
   ``ColumnMeta.masked`` is set. The masked rows are what get
   persisted to the accepted-query history.

Errors are surfaced with sanitized i18n keys — never raw SQL,
column, table, schema, UUID, host, port, or user values.
"""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, NoReturn

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.services.detection  # noqa: F401 — registers built-in rules into REGISTRY
from app.core.attempt_store import EphemeralAttempt, delete_attempt, get_attempt, store_attempt
from app.core.config import get_settings
from app.core.exceptions import (
    AttemptContextInvalid,
    AttemptNotFound,
    AttemptOwnershipViolation,
    DetectionUnavailableError,
    LLMTimeout,
    PolicySchemaConflictError,
    QuotaExceededError,
    QuotaUnavailableError,
    SessionInvalidated,
    SourceDBConnectionFailed,
    SourceDBPermissionDenied,
    SourceDBTimeout,
)
from app.core.processing_lock import acquire_lock, release_lock_if_owned
from app.core.query_deadline import (
    QueryDeadline,
    QueryDeadlineExpired,
    query_lock_ttl_seconds,
)
from app.core.session_cancellation import (
    QueryOperation,
    TrackedAttempt,
    clear_query_operation_if_owned,
    discard_session_attempt_if_owned,
    ensure_session_active,
    register_query_operation,
    run_cancellable_session_stage,
    track_session_attempt,
)
from app.db.models.enums import AuditActionType
from app.db.models.user import User
from app.evaluator.rules.role_authorization import RoleAuthorizationRule
from app.evaluator.schema_context import SchemaContext
from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.repositories.detection_config_repository import DetectionConfigRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.query import (
    AcceptedQuerySummary,
    ColumnMeta,
    EvaluatorRejection,
    QueryResult,
    RefinePrompt,
    Violation,
)
from app.services.audit_service import AuditService
from app.services.detection.audit_representation import build_detection_audit_context
from app.services.detection.detector import HostileInputDetector
from app.services.policy_enforcement import (
    PolicyEnforcementService,
)


@dataclass(frozen=True)
class RolePolicy:
    """Resolved role policy for a (user, connection) pair (T-712).

    Constructed by the ``role_policy_provider`` callback passed to
    ``QueryService``. The provider looks up the user's role and the
    matching ``role_connection_policies`` row for the connection and
    returns the resolved policy.

    A ``None`` return from the provider means "no policy applies" —
    backward-compatible with the Phase 1-3 un-authenticated flow
    (no schema filter, no role auth rule, no row filter, no mask).
    """

    user_id: uuid.UUID
    role_id: uuid.UUID
    connection_id: uuid.UUID
    allowed_tables: list[dict] = field(default_factory=list)
    row_filters: list[dict] = field(default_factory=list)
    column_masks: list[dict] | None = None
    user_context: dict[str, Any] = field(default_factory=dict)


# Type alias for the policy provider callback.
RolePolicyProvider = Callable[[uuid.UUID, uuid.UUID], Awaitable[RolePolicy | None]]


@dataclass(frozen=True)
class _ExecutionFailureAudit:
    action: AuditActionType
    actor_id: uuid.UUID
    resource_type: str
    resource_id: str
    reason: str
    actor_identity: str | None = None


@dataclass(frozen=True)
class _TimeoutFailure:
    audit: _ExecutionFailureAudit
    attempt: EphemeralAttempt | None = None
    http_session_id: str | None = None
    chat_session_id: str | None = None
    tracked_attempt: TrackedAttempt | None = None


@dataclass(frozen=True)
class _RetryAuditEvent:
    action: AuditActionType
    actor_id: uuid.UUID
    actor_identity: str | None
    attempt_id: str
    outcome: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _RetryRequest:
    attempt_id: str
    http_session_id: str
    user_id: str
    decision_action: AuditActionType | None = None


@dataclass(frozen=True)
class _RejectedRetry:
    prior_attempt_id: str
    retry_attempt_id: str
    http_session_id: str
    chat_session_id: str
    user_id: str
    database_connection_id: uuid.UUID | None
    sql: str
    question: str
    attempt_number: int
    violations: list[dict[str, str]]


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively convert Decimal (and other non-JSON types) to JSON-safe values."""
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(item) for item in obj]
    return obj


def _source_failure_response(source_error: Exception) -> tuple[int, dict[str, str], str]:
    """Return the sanitized HTTP and audit contract for a source failure."""
    if isinstance(source_error, SourceDBPermissionDenied):
        return (
            status.HTTP_403_FORBIDDEN,
            {"error": "forbidden", "message_key": "error.forbidden"},
            "permission_denied",
        )
    if isinstance(source_error, SourceDBConnectionFailed):
        return (
            status.HTTP_502_BAD_GATEWAY,
            {
                "error": "source_db_connection_failed",
                "message_key": "error.sourceDbConnectionFailed",
            },
            "connection_failed",
        )
    return (
        status.HTTP_502_BAD_GATEWAY,
        {
            "error": "source_db_execution_failed",
            "message_key": "error.sourceDbExecutionFailed",
        },
        "execution_failed",
    )


class QueryService:
    """Orchestrates the question-to-result lifecycle."""

    def __init__(
        self,
        accepted_query_repository: AcceptedQueryRepository,
        session_repository: SessionRepository,
        db_session: AsyncSession,
        redis: Redis,
        llm: Any,
        evaluator: Any,
        source_db_executor: Any,
        llm_provider: str = "",
        schema_context: SchemaContext | str = "",
        target_dialect: str | None = None,
        connection_id: str | None = None,
        source_db_adapter: Any = None,
        policy_enforcement: PolicyEnforcementService | None = None,
        role_policy_provider: RolePolicyProvider | None = None,
        quota_service: Any = None,
        query_timeout_seconds: int | None = None,
        monotonic_clock: Callable[[], float] | None = None,
    ) -> None:
        self._repo = accepted_query_repository
        self._session_repo = session_repository
        self._db_session = db_session
        self._redis = redis
        self._llm = llm
        self._evaluator = evaluator
        self._executor = source_db_executor
        self._llm_provider = llm_provider
        self._schema_context = schema_context
        self._target_dialect = target_dialect
        self._connection_id = connection_id
        self._adapter = source_db_adapter
        self._policy = policy_enforcement or PolicyEnforcementService()
        self._role_policy_provider = role_policy_provider
        self._quota_service = quota_service
        if query_timeout_seconds is None:
            query_timeout_seconds = get_settings().QUERY_TIMEOUT_SECONDS
        self._query_timeout_seconds = query_timeout_seconds
        self._monotonic_clock = monotonic_clock

    async def _acquire_lock(self, session_id: str, ttl: int) -> str | None:
        """Try to acquire a per-session processing lock.

        Returns an owner token (uuid string) if acquired, None if already held.
        """
        return await acquire_lock(session_id, self._redis, ttl=ttl)

    async def _release_lock_if_owned(self, session_id: str, owner: str | None) -> bool:
        """Release the processing lock only if we own it."""
        return await release_lock_if_owned(session_id, owner, self._redis)

    def _start_query_deadline(self) -> QueryDeadline:
        deadline = QueryDeadline.start(
            self._query_timeout_seconds,
            clock=self._monotonic_clock,
        )
        deadline.arm_current_task()
        return deadline

    @property
    def _query_lock_ttl(self) -> int:
        return query_lock_ttl_seconds(self._query_timeout_seconds)

    async def _ensure_chat_session_active(self, chat_session_id: str | None) -> None:
        if chat_session_id is not None:
            await ensure_session_active(chat_session_id, self._redis)

    async def _ensure_operation_active(
        self,
        chat_session_id: str | None,
        deadline: QueryDeadline,
    ) -> None:
        await self._ensure_chat_session_active(chat_session_id)
        deadline.ensure_active()

    async def _run_chat_session_stage(
        self,
        chat_session_id: str | None,
        user_id: str,
        stage: Awaitable[Any],
    ) -> Any:
        if chat_session_id is None:
            return await stage
        return await run_cancellable_session_stage(chat_session_id, user_id, stage)

    async def _discard_invalidated_attempt(self, tracked_attempt: TrackedAttempt | None) -> None:
        await self._db_session.rollback()
        if tracked_attempt is not None:
            await discard_session_attempt_if_owned(tracked_attempt, self._redis)

    async def _persist_audit_without_request_side_effects(
        self,
        *,
        action: AuditActionType,
        actor_id: uuid.UUID,
        outcome: str,
        context: dict[str, Any],
        actor_identity: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> None:
        """Rollback pending work, then persist one sanitized audit event."""
        await self._db_session.rollback()
        await self._log_audit_durably(
            action=action,
            actor_id=actor_id,
            actor_identity=actor_identity,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            context=context,
        )

    async def _log_audit_durably(
        self,
        *,
        action: AuditActionType,
        actor_id: uuid.UUID,
        outcome: str,
        context: dict[str, Any],
        actor_identity: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> None:
        """Commit one audit event independently of request-side mutations."""
        audit_kwargs: dict[str, Any] = {
            "action": action,
            "actor_id": actor_id,
            "outcome": outcome,
            "context": context,
        }
        if actor_identity is not None:
            audit_kwargs["actor_identity"] = actor_identity
        if resource_type is not None:
            audit_kwargs["resource_type"] = resource_type
        if resource_id is not None:
            audit_kwargs["resource_id"] = resource_id

        if not isinstance(self._db_session, AsyncSession):
            await AuditService.log(self._db_session, **audit_kwargs)
            await self._db_session.commit()
            return

        audit_session_factory = async_sessionmaker(
            bind=self._db_session.bind,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with audit_session_factory() as audit_session:
            await AuditService.log(audit_session, **audit_kwargs)
            await audit_session.commit()

    async def _persist_quota_exceeded_audit(
        self,
        user_id: uuid.UUID,
        dimension: str,
        reset_at: str,
    ) -> None:
        """Persist a quota denial without committing pending request side effects."""
        await self._persist_audit_without_request_side_effects(
            action=AuditActionType.QUOTA_EXCEEDED,
            actor_id=user_id,
            outcome="blocked",
            context={
                "dimension": dimension,
                "reset_at": reset_at,
            },
        )

    async def _persist_execution_failure_audit(self, event: _ExecutionFailureAudit) -> None:
        """Persist a sanitized failure without committing pending request work."""
        await self._persist_audit_without_request_side_effects(
            action=event.action,
            actor_id=event.actor_id,
            actor_identity=event.actor_identity,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            outcome="failure",
            context={"reason": event.reason},
        )

    async def _persist_retry_audit(self, event: _RetryAuditEvent) -> None:
        await self._log_audit_durably(
            action=event.action,
            actor_id=event.actor_id,
            actor_identity=event.actor_identity,
            resource_type="query_attempt",
            resource_id=event.attempt_id,
            outcome=event.outcome,
            context=event.context,
        )

    async def _consume_retry_quota(
        self,
        user: User,
        dimension: str,
        chat_session_id: str,
        deadline: QueryDeadline,
    ) -> None:
        if self._quota_service is None or user.role_id is None:
            return
        try:
            await self._quota_service.check_and_increment(user.id, user.role_id, dimension)
        except QuotaExceededError as exc:
            await self._ensure_operation_active(chat_session_id, deadline)
            await self._persist_quota_exceeded_audit(user.id, dimension, exc.reset_at)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "quota_exceeded",
                    "message_key": "error.quota_exceeded",
                    "reset_at": exc.reset_at,
                },
            ) from exc
        except QuotaUnavailableError as exc:
            await self._ensure_operation_active(chat_session_id, deadline)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "service_unavailable",
                    "message_key": "error.service_unavailable",
                },
            ) from exc

    async def _store_rejected_retry(
        self,
        rejection: _RejectedRetry,
        deadline: QueryDeadline,
    ) -> tuple[EphemeralAttempt, TrackedAttempt]:
        """Replace a prior attempt with one sanitized rejected retry record."""
        failed_attempt = EphemeralAttempt(
            attempt_id=rejection.retry_attempt_id,
            session_id=rejection.http_session_id,
            chat_session_id=rejection.chat_session_id,
            user_id=rejection.user_id,
            database_connection_id=rejection.database_connection_id,
            sql=rejection.sql,
            question=rejection.question,
            attempt_number=rejection.attempt_number,
            llm_provider=self._llm_provider,
            state="REJECTED",
            evaluator_result={
                "passed": False,
                "violations": rejection.violations,
            },
        )
        tracked_attempt = TrackedAttempt(
            session_id=rejection.chat_session_id,
            user_id=rejection.user_id,
            http_session_id=rejection.http_session_id,
            attempt_id=rejection.retry_attempt_id,
        )
        await track_session_attempt(tracked_attempt, self._redis)
        await self._ensure_operation_active(rejection.chat_session_id, deadline)
        await store_attempt(failed_attempt, rejection.http_session_id, self._redis)
        await delete_attempt(rejection.prior_attempt_id, self._redis)
        await self._ensure_operation_active(rejection.chat_session_id, deadline)
        await self._redis.delete(f"active_attempt:{rejection.http_session_id}")
        return failed_attempt, tracked_attempt

    async def _raise_timeout(self, failure: _TimeoutFailure, cause: BaseException) -> NoReturn:
        try:
            await self._ensure_chat_session_active(failure.chat_session_id)
            if failure.attempt is not None and failure.http_session_id is not None:
                failure.attempt.state = "TIMEOUT"
                await store_attempt(failure.attempt, failure.http_session_id, self._redis)
            if failure.http_session_id is not None:
                await self._redis.delete(f"active_attempt:{failure.http_session_id}")
            await self._ensure_chat_session_active(failure.chat_session_id)
        except SessionInvalidated:
            await self._discard_invalidated_attempt(failure.tracked_attempt)
            raise

        await self._persist_execution_failure_audit(failure.audit)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"error": "timeout", "message_key": "error.timeout"},
        ) from cause

    async def _get_llm_context_cap(self) -> int:
        """Read llm_context_cap from app_config (default 3)."""
        result = await self._db_session.execute(text("SELECT value FROM app_config WHERE key = 'llm_context_cap'"))
        row = result.fetchone()
        if row is not None:
            return int(row[0])
        return 3

    async def _get_max_regenerate_attempts(self) -> int:
        """Read max_regenerate_attempts from app_config (default 3 = 3 regen clicks after original)."""
        result = await self._db_session.execute(
            text("SELECT value FROM app_config WHERE key = 'max_regenerate_attempts'")
        )
        row = result.fetchone()
        if row is not None:
            return int(row[0])
        return 3

    async def _get_database_connection_id(self) -> str:
        """Return the explicitly scoped source connection ID."""
        if self._connection_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "config_error", "message_key": "error.sourceDbNotConfigured"},
            )
        return self._connection_id

    def _require_attempt_binding(self, attempt: EphemeralAttempt, user_id: str) -> str:
        """Validate that the loaded attempt still matches this service and user."""
        connection_id = str(attempt.database_connection_id)
        if attempt.user_id != user_id or self._connection_id != connection_id:
            raise AttemptContextInvalid()
        return connection_id

    async def ensure_connection_authorized(self, user_id: str) -> None:
        """Fail closed when the user's current policy revoked this connection."""
        policy = await self._resolve_role_policy(user_id, await self._get_database_connection_id())
        if policy is not None and not policy.allowed_tables:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=self._role_auth_rejection().model_dump(),
            )

    async def _resolve_role_policy(
        self,
        user_id: str,
        connection_id: str | None,
    ) -> RolePolicy | None:
        """Look up the role policy for (user_id, connection_id).

        Returns ``None`` ONLY when the provider is not configured
        (Phase 1-3 backward compat) or the user has no ``role_id``.
        For role-bearing users the provider always returns a
        ``RolePolicy`` (either the resolved row or a deny-all) so
        the caller can fail closed. See
        ``app.services.role_policy_provider`` for the full
        fail-closed contract.
        """
        if self._role_policy_provider is None:
            return None
        user_uuid = uuid.UUID(user_id)
        conn_uuid = uuid.UUID(connection_id) if connection_id else uuid.UUID(await self._get_database_connection_id())
        return await self._role_policy_provider(user_uuid, conn_uuid)

    def _policy_schema_for_prompt(
        self,
        policy: RolePolicy | None,
        base_schema: Any,
    ) -> Any:
        """Return the schema (object or string) to send to the LLM.

        When a policy with a non-empty ``allowed_tables`` exists, the
        schema is filtered so the LLM only sees role-permitted
        tables/columns (FR-128 / S-006). The input schema object is
        never mutated (``PolicyEnforcementService.filter_schema``
        returns a new instance).

        When ``policy`` is ``None`` or has an empty ``allowed_tables``
        the caller is responsible for the fail-closed check; this
        helper does not enforce that — it just returns the base
        schema for the LLM.
        """
        if policy is None:
            return base_schema
        if not policy.allowed_tables:
            return base_schema
        if not isinstance(base_schema, SchemaContext):
            # Backward compat: if a string was passed in (legacy
            # tests), pass it through. Production passes a
            # SchemaContext.
            return base_schema
        return self._policy.filter_schema(base_schema, policy.allowed_tables)

    def _role_auth_rejection(self) -> EvaluatorRejection:
        """Build a sanitized rejection for a role-auth failure.

        Reason: the LLM was either blocked from being called (empty
        policy) or generated SQL that referenced tables/columns
        outside the role's policy. The response uses the constant
        i18n key ``error.queryBlockedPolicy`` per FR-130 / S-007
        and the api-contracts.md line 385 contract. No table,
        column, or SQL value is leaked.
        """
        return EvaluatorRejection(
            message_key="error.queryBlockedPolicy",
            violations=[
                Violation(
                    rule="role_authorization",
                    message_key="error.queryBlockedPolicy",
                )
            ],
        )

    async def _enforce_role_authorization(
        self,
        sql: str,
        policy: RolePolicy | None,
    ) -> EvaluatorRejection | None:
        """Run the ``RoleAuthorizationRule`` against *sql*.

        Returns an ``EvaluatorRejection`` if the SQL is outside the
        role's ``allowed_tables`` policy, or ``None`` if the SQL
        passes. No-op when ``policy`` is ``None`` or has empty
        ``allowed_tables`` (the latter is enforced earlier in the
        flow as a fail-closed pre-LLM rejection).
        """
        if policy is None or not policy.allowed_tables:
            return None
        rule = RoleAuthorizationRule(
            allowed_tables=policy.allowed_tables,
            dialect=self._target_dialect or "postgres",
        )
        passed, _reason = await rule.evaluate(sql, self._schema_context)
        if not passed:
            return self._role_auth_rejection()
        return None

    async def submit_question(
        self,
        http_session_id: str,
        user_id: str,
        question: str,
        chat_session_id: str | None = None,
        connection_id: str | None = None,
    ) -> QueryResult | EvaluatorRejection:
        """Submit a question: LLM -> evaluate -> execute -> result."""
        lock_owner = await self._acquire_lock(http_session_id, ttl=self._query_lock_ttl)
        if lock_owner is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "concurrent", "message_key": "error.concurrent"},
            )

        deadline = self._start_query_deadline()
        user_uuid = uuid.UUID(user_id)
        attempt_id = str(uuid.uuid4())
        attempt: EphemeralAttempt | None = None
        actor_identity: str | None = None
        query_operation: QueryOperation | None = None
        tracked_attempt: TrackedAttempt | None = None
        try:
            # Verify user exists in DB (guard against stale Redis sessions)
            result = await self._db_session.execute(select(User).where(User.id == user_uuid))
            user_row = result.scalar_one_or_none()
            if user_row is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error": "unauthorized", "message_key": "error.unauthorized"},
                )
            actor_identity = getattr(user_row, "username", None)
            deadline.ensure_active()

            # T-845: Hostile input detection FIRST — before quota check.
            # Blocked requests: emit HOSTILE_INPUT_BLOCKED audit (redacted context)
            #   and return 400 immediately. Quota counter NOT incremented.
            # Flagged requests: emit HOSTILE_INPUT_FLAGGED audit, continue to quota.
            # Allowed requests: proceed normally.
            try:
                _detection_config_repo = DetectionConfigRepository(self._db_session)
                _detection_thresholds = await _detection_config_repo.get_for_detection()
                _detector = HostileInputDetector()
                _detection_outcome = await _detector.detect(question, _detection_thresholds)
            except DetectionUnavailableError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "error": "service_unavailable",
                        "message_key": "error.service_unavailable",
                    },
                ) from None
            deadline.ensure_active()
            _detection_context = build_detection_audit_context(
                outcome=_detection_outcome.outcome,
                results=_detection_outcome.results,
                text=question,
            )
            if _detection_outcome.outcome == "blocked":
                # Emit HOSTILE_INPUT_BLOCKED audit with redacted context only.
                # Raw hostile text MUST NOT appear in context.
                await AuditService.log(
                    self._db_session,
                    action=AuditActionType.HOSTILE_INPUT_BLOCKED,
                    actor_id=user_uuid,
                    actor_identity=getattr(user_row, "username", None),
                    resource_type="query_attempt",
                    outcome="blocked",
                    context=_detection_context,
                )
                # The request exits via HTTPException, so persist the security
                # event before the request-scoped transaction is rolled back.
                await self._db_session.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "hostile_input_blocked",
                        "message_key": "error.hostile_input_blocked",
                    },
                )
            if _detection_outcome.outcome == "flagged":
                # Emit HOSTILE_INPUT_FLAGGED audit; request continues.
                await AuditService.log(
                    self._db_session,
                    action=AuditActionType.HOSTILE_INPUT_FLAGGED,
                    actor_id=user_uuid,
                    actor_identity=getattr(user_row, "username", None),
                    resource_type="query_attempt",
                    outcome="flagged",
                    context=_detection_context,
                )
                # Downstream quota or generation failures roll back their own
                # transaction; preserve the security event before continuing.
                await self._db_session.commit()
            deadline.ensure_active()

            # T-800/T-845: Query quota check immediately after hostile input detection.
            # Non-hostile requests spend query quota before chat session, attempt,
            # policy, or LLM side effects. Blocked hostile requests return above
            # without incrementing quota.
            if self._quota_service is not None:
                user_role_id = getattr(user_row, "role_id", None)
                if user_role_id is not None:
                    try:
                        await self._quota_service.check_and_increment(user_uuid, user_role_id, "queries")
                    except QuotaExceededError as exc:
                        await self._persist_quota_exceeded_audit(
                            user_uuid,
                            "queries",
                            exc.reset_at,
                        )
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail={
                                "error": "quota_exceeded",
                                "message_key": "error.quota_exceeded",
                                "reset_at": exc.reset_at,
                            },
                        ) from exc
                    except QuotaUnavailableError as exc:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail={
                                "error": "service_unavailable",
                                "message_key": "error.service_unavailable",
                            },
                        ) from exc
            deadline.ensure_active()

            # Lazy session creation
            if chat_session_id is None:
                new_session = await self._session_repo.create(
                    user_id=user_uuid,
                    preview_text=question,
                )
                chat_session_id = str(new_session.id)
            else:
                # Validate session exists and belongs to user
                sess = await self._session_repo.get_by_id(uuid.UUID(chat_session_id), user_uuid)
                if sess is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail={"error": "not_found", "message_key": "error.notFound"},
                    )
                # Apply implicit feedback on follow-up (FR-036a)
                latest = await self._repo.get_latest_by_session(uuid.UUID(chat_session_id), user_uuid)
                if latest is not None and latest.feedback is None:
                    latest.feedback = 1
                    latest.saved = True
                    await self._db_session.flush()
                # Update last_activity and preview_text if empty
                await self._session_repo.update_last_activity(uuid.UUID(chat_session_id), user_uuid)
                if not sess.preview_text:
                    await self._session_repo.update_preview_text(uuid.UUID(chat_session_id), user_uuid, question)

            deadline.ensure_active()
            source_connection_id = await self._get_database_connection_id()
            if connection_id is not None and uuid.UUID(connection_id) != uuid.UUID(source_connection_id):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "attempt_invalid", "message_key": "error.attemptInvalid"},
                )

            attempt = EphemeralAttempt(
                attempt_id=attempt_id,
                session_id=http_session_id,
                chat_session_id=chat_session_id,
                user_id=user_id,
                database_connection_id=uuid.UUID(source_connection_id),
                question=question,
                state="PENDING",
                llm_provider=self._llm_provider,
            )

            await self._ensure_operation_active(chat_session_id, deadline)
            if chat_session_id is not None:
                query_operation = QueryOperation(
                    session_id=chat_session_id,
                    user_id=user_id,
                    http_session_id=http_session_id,
                    attempt_id=attempt_id,
                    lock_owner=lock_owner,
                    token=str(uuid.uuid4()),
                )
                if not await register_query_operation(query_operation, self._redis):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"error": "concurrent", "message_key": "error.concurrent"},
                    )
                tracked_attempt = TrackedAttempt(
                    session_id=chat_session_id,
                    user_id=user_id,
                    http_session_id=http_session_id,
                    attempt_id=attempt_id,
                )
                await track_session_attempt(tracked_attempt, self._redis)
                await self._ensure_operation_active(chat_session_id, deadline)
            await store_attempt(attempt, http_session_id, self._redis)
            await self._ensure_operation_active(chat_session_id, deadline)

            # FR-140: emit a tamper-evident query.submit audit
            # entry on every submission attempt. Context carries
            # the question length (never the question text —
            # users may paste secrets into the question) and
            # the target dialect. No SQL, no row data, no
            # credentials, no driver internals.
            await AuditService.log(
                self._db_session,
                action=AuditActionType.QUERY_SUBMIT,
                actor_id=user_uuid,
                actor_identity=getattr(user_row, "username", None),
                resource_type="query_attempt",
                resource_id=attempt_id,
                outcome="success",
                context={
                    "question_length": len(question),
                    "dialect": self._target_dialect or "postgres",
                },
            )
            await self._ensure_operation_active(chat_session_id, deadline)

            # T-712: Resolve role policy. When the user has a role_id
            # and a connection-scoped policy exists, the LLM prompt
            # is filtered to role-allowed schema and a
            # ``RoleAuthorizationRule`` is added to the evaluator
            # pipeline. When the user has no role_id (Phase 1-3
            # backwards compat) the provider returns ``None`` and
            # every policy step is a no-op.
            role_policy = await self._resolve_role_policy(
                user_id,
                source_connection_id,
            )
            await self._ensure_operation_active(chat_session_id, deadline)
            if role_policy is not None and not role_policy.allowed_tables:
                # Deny-all policy: fail closed before the LLM so the
                # user never gets a prompt that mentions any table.
                attempt.state = "REJECTED"
                attempt.evaluator_result = {
                    "passed": False,
                    "violations": [{"rule": "role_authorization", "message_key": "error.queryBlockedPolicy"}],
                }
                await store_attempt(attempt, http_session_id, self._redis)
                # FR-140: audit the policy block. Context carries
                # the constant reason; no table / column / schema /
                # SQL / user values leak.
                await self._persist_audit_without_request_side_effects(
                    action=AuditActionType.ACCESS_DENIED,
                    actor_id=user_uuid,
                    actor_identity=getattr(user_row, "username", None),
                    resource_type="query_attempt",
                    resource_id=attempt_id,
                    outcome="denied",
                    context={"reason": "deny_all"},
                )
                await self._ensure_operation_active(chat_session_id, deadline)
                return self._role_auth_rejection()

            # Load conversation history for context
            conversation_history: list[dict] = []
            if chat_session_id:
                cap = await self._get_llm_context_cap()
                if cap > 0:
                    prior_attempts = await self._repo.list_by_session(uuid.UUID(chat_session_id), user_uuid, limit=cap)
                    # Reverse to chronological order for prompt
                    for a in reversed(prior_attempts):
                        conversation_history.append(
                            {
                                "question": a.question_text,
                                "sql": a.generated_sql,
                            }
                        )

            # 1. LLM generation
            schema_for_prompt = self._policy_schema_for_prompt(
                role_policy,
                self._schema_context,
            )
            await self._ensure_operation_active(chat_session_id, deadline)
            try:
                sql = await self._run_chat_session_stage(
                    chat_session_id,
                    user_id,
                    self._llm.generate_sql(
                        question=question,
                        schema_context=schema_for_prompt,
                        conversation_history=conversation_history or None,
                        target_dialect=self._target_dialect,
                        timeout=deadline.remaining_seconds(),
                    ),
                )
            except asyncio.CancelledError:
                await self._ensure_chat_session_active(chat_session_id)
                raise
            except LLMTimeout as exc:
                raise QueryDeadlineExpired() from exc
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"error": "llm_unavailable", "message_key": "error.llmUnavailable"},
                ) from exc
            await self._ensure_operation_active(chat_session_id, deadline)

            attempt.sql = sql
            attempt.state = "GENERATED"
            await store_attempt(attempt, http_session_id, self._redis)
            await self._ensure_operation_active(chat_session_id, deadline)

            # 2. Evaluator gate (existing rules)
            try:
                eval_result = await self._run_chat_session_stage(
                    chat_session_id,
                    user_id,
                    self._evaluator.evaluate(sql, None),
                )
            except asyncio.CancelledError:
                await self._ensure_chat_session_active(chat_session_id)
                raise
            await self._ensure_operation_active(chat_session_id, deadline)
            if not eval_result.passed:
                attempt.state = "REJECTED"
                attempt.evaluator_result = {
                    "passed": False,
                    "violations": [{"rule": v.rule_name, "message_key": v.message_key} for v in eval_result.violations],
                }
                await store_attempt(attempt, http_session_id, self._redis)
                # FR-140: emit query.validate.fail. Context carries
                # the rule names only (safe strings); no SQL, no
                # schema, no question text.
                await self._persist_audit_without_request_side_effects(
                    action=AuditActionType.QUERY_VALIDATE_FAIL,
                    actor_id=user_uuid,
                    actor_identity=getattr(user_row, "username", None),
                    resource_type="query_attempt",
                    resource_id=attempt_id,
                    outcome="failure",
                    context={
                        "rules": [v.rule_name for v in eval_result.violations],
                    },
                )
                await self._ensure_operation_active(chat_session_id, deadline)
                violations = [Violation(rule=v.rule_name, message_key=v.message_key) for v in eval_result.violations]
                return EvaluatorRejection(
                    message_key="query.evaluator.rejected",
                    violations=violations,
                )

            # 2a. T-712: Policy-based role authorization. Runs after
            # the existing evaluator and before the executor. Uses
            # the role's allowed_tables to build a fresh
            # RoleAuthorizationRule. Failure surfaces as a sanitized
            # EvaluatorRejection with error.queryBlockedPolicy.
            # FR-140: emit query.validate.pass BEFORE the
            # role-authorization check; if role-auth then blocks,
            # a separate access.denied entry is emitted (constant
            # reason; no SQL / table / column leak).
            await AuditService.log(
                self._db_session,
                action=AuditActionType.QUERY_VALIDATE_PASS,
                actor_id=user_uuid,
                actor_identity=getattr(user_row, "username", None),
                resource_type="query_attempt",
                resource_id=attempt_id,
                outcome="success",
                context={},
            )
            await self._ensure_operation_active(chat_session_id, deadline)
            role_auth_rejection = await self._enforce_role_authorization(sql, role_policy)
            await self._ensure_operation_active(chat_session_id, deadline)
            if role_auth_rejection is not None:
                attempt.state = "REJECTED"
                attempt.evaluator_result = {
                    "passed": False,
                    "violations": [
                        {"rule": v.rule, "message_key": v.message_key} for v in role_auth_rejection.violations
                    ],
                }
                await store_attempt(attempt, http_session_id, self._redis)
                await self._persist_audit_without_request_side_effects(
                    action=AuditActionType.ACCESS_DENIED,
                    actor_id=user_uuid,
                    actor_identity=getattr(user_row, "username", None),
                    resource_type="query_attempt",
                    resource_id=attempt_id,
                    outcome="denied",
                    context={"reason": "role_authorization"},
                )
                await self._ensure_operation_active(chat_session_id, deadline)
                return role_auth_rejection

            attempt.state = "EVALUATED"
            await store_attempt(attempt, http_session_id, self._redis)
            await self._ensure_operation_active(chat_session_id, deadline)

            # 3. T-712: Apply per-role row filters via
            # PolicyEnforcementService.apply_row_filters. Returns a
            # ``BoundSql`` with the rewritten SQL and the bound
            # parameter tuple. When no policy applies (legacy
            # Phase 1-3) the SQL passes through unchanged with
            # ``params = ()``. ``PolicySchemaConflictError`` is
            # caught below and translated to a sanitized
            # ``error.policySchemaConflict`` HTTP 409.
            row_filter_params: tuple[Any, ...] = ()
            effective_sql = sql
            if role_policy is not None and role_policy.row_filters:
                try:
                    bound = self._policy.apply_row_filters(
                        sql=sql,
                        row_filters=role_policy.row_filters,
                        schema=self._schema_context
                        if isinstance(self._schema_context, SchemaContext)
                        else SchemaContext(tables=[]),
                        user_context=role_policy.user_context,
                        dialect=self._target_dialect or "postgres",
                    )
                except PolicySchemaConflictError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={
                            "error": "policy_schema_conflict",
                            "message_key": "error.policySchemaConflict",
                        },
                    ) from exc
                effective_sql = bound.sql
                row_filter_params = bound.params
            await self._ensure_operation_active(chat_session_id, deadline)

            # T-802: Execution quota check before SQL execution.
            # If QuotaService is wired, check the "executions" dimension
            # before the source DB executor call. Fail-closed.
            if self._quota_service is not None:
                user_role_id = getattr(user_row, "role_id", None)
                if user_role_id is not None:
                    try:
                        await self._quota_service.check_and_increment(user_uuid, user_role_id, "executions")
                    except QuotaExceededError as exc:
                        await self._persist_quota_exceeded_audit(
                            user_uuid,
                            "executions",
                            exc.reset_at,
                        )
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail={
                                "error": "quota_exceeded",
                                "message_key": "error.quota_exceeded",
                                "reset_at": exc.reset_at,
                            },
                        ) from exc
                    except QuotaUnavailableError as exc:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail={
                                "error": "service_unavailable",
                                "message_key": "error.service_unavailable",
                            },
                        ) from exc
            await self._ensure_operation_active(chat_session_id, deadline)

            # 4. Execute against source DB. Adapter and legacy
            # executor both receive the rewritten SQL + row-filter
            # params. asyncpg positional binding is used; the
            # adapter's ``execute(sql, params)`` signature accepts
            # the tuple unchanged.
            await self._ensure_operation_active(chat_session_id, deadline)
            try:
                source_timeout = deadline.remaining_seconds()
                if self._adapter is not None:
                    exec_result = await self._run_chat_session_stage(
                        chat_session_id,
                        user_id,
                        self._adapter.execute(
                            effective_sql,
                            row_filter_params,
                            timeout=source_timeout,
                        ),
                    )
                    columns, rows = exec_result.columns, exec_result.rows
                else:
                    columns, rows = await self._run_chat_session_stage(
                        chat_session_id,
                        user_id,
                        self._executor.execute(
                            effective_sql,
                            timeout=source_timeout,
                            params=row_filter_params,
                        ),
                    )
            except asyncio.CancelledError:
                await self._ensure_chat_session_active(chat_session_id)
                attempt.state = "FAILED"
                await store_attempt(attempt, http_session_id, self._redis)
                raise
            except (TimeoutError, SourceDBTimeout) as exc:
                raise QueryDeadlineExpired() from exc
            except Exception as exc:
                # The source adapter is an external boundary. Collapse every
                # non-timeout driver failure before it can reach HTTP or logs.
                failure_status, failure_detail, failure_reason = _source_failure_response(exc)
                attempt.state = "FAILED"
                await store_attempt(attempt, http_session_id, self._redis)
                await self._persist_execution_failure_audit(
                    _ExecutionFailureAudit(
                        action=AuditActionType.QUERY_EXECUTE,
                        actor_id=user_uuid,
                        actor_identity=getattr(user_row, "username", None),
                        resource_type="query_attempt",
                        resource_id=attempt_id,
                        reason=failure_reason,
                    )
                )
                raise HTTPException(
                    status_code=failure_status,
                    detail=failure_detail,
                ) from None
            await self._ensure_operation_active(chat_session_id, deadline)

            # 4a. T-712: Apply per-role column masks to the
            # ``QueryResult`` after execution. Returns a new
            # ``QueryResult`` with masked values (``"***"``) and
            # ``ColumnMeta.masked = True``. When no policy applies
            # this is a no-op that returns an original-equivalent
            # ``QueryResult`` (input not mutated). The masked rows
            # are what get persisted to the accepted-query history
            # — unmasked sensitive values never touch the response
            # or the DB.
            await self._ensure_operation_active(chat_session_id, deadline)
            column_metas = []
            for c in columns:
                if isinstance(c, dict):
                    column_metas.append(ColumnMeta(name=c["name"], type=c["type"]))
                else:
                    column_metas.append(ColumnMeta(name=c, type="text"))
            masked_result = QueryResult(
                kind="result",
                attempt_id=attempt_id,
                session_id=chat_session_id,
                question=question,
                generated_sql=sql,
                columns=column_metas,
                rows=rows,
                row_count=len(rows),
                attempt_number=1,
                is_last_auto_retry=False,
            )
            if role_policy is not None and role_policy.column_masks:
                masked_result = self._policy.apply_column_masks(
                    masked_result,
                    role_policy.column_masks,
                    dialect=self._target_dialect,
                )
                # Refresh ColumnMeta list from the masked result so
                # the masked flags are reflected in the response.
                column_metas = list(masked_result.columns)
                rows = masked_result.rows
            result = masked_result

            await self._ensure_operation_active(chat_session_id, deadline)
            attempt.state = "EXECUTED"
            await store_attempt(attempt, http_session_id, self._redis)
            await self._ensure_operation_active(chat_session_id, deadline)

            # 5. Auto-save (idempotent: skip if already persisted for this attempt_id)
            await self._ensure_operation_active(chat_session_id, deadline)
            session_uuid = uuid.UUID(chat_session_id) if chat_session_id else None
            db_conn_id = await self._get_database_connection_id()
            existing = await self._repo.get_by_attempt_id(attempt_id, user_uuid)
            if existing is None:
                saved_query = await self._repo.create(
                    user_id=user_uuid,
                    database_connection_id=uuid.UUID(db_conn_id),
                    question_text=question,
                    generated_sql=sql,
                    llm_provider=self._llm_provider,
                    attempt_id=attempt_id,
                    session_id=session_uuid,
                    saved=True,
                    feedback=1,
                    result_columns=[c.model_dump() for c in column_metas],
                    result_rows=_sanitize_for_json(rows),
                    result_row_count=len(rows),
                )
                result.accepted_query_id = str(saved_query.id)
            else:
                result.accepted_query_id = str(existing.id)

            await self._ensure_operation_active(chat_session_id, deadline)

            # Track active attempt for session (G-001+G-004)
            await self._redis.set(f"active_attempt:{http_session_id}", attempt_id)

            await self._ensure_operation_active(chat_session_id, deadline)
            await AuditService.log(
                self._db_session,
                action=AuditActionType.QUERY_EXECUTE,
                actor_id=user_uuid,
                actor_identity=actor_identity,
                resource_type="query_attempt",
                resource_id=attempt_id,
                outcome="success",
                context={"row_count": len(rows)},
            )
            await self._ensure_operation_active(chat_session_id, deadline)
            return result
        except SessionInvalidated:
            await self._discard_invalidated_attempt(tracked_attempt)
            raise
        except (QueryDeadlineExpired, asyncio.CancelledError) as exc:
            if isinstance(exc, asyncio.CancelledError) and not deadline.cancelled_current_task:
                raise
            deadline.disarm()
            await self._raise_timeout(
                _TimeoutFailure(
                    audit=_ExecutionFailureAudit(
                        action=AuditActionType.QUERY_EXECUTE,
                        actor_id=user_uuid,
                        actor_identity=actor_identity,
                        resource_type="query_attempt",
                        resource_id=attempt_id,
                        reason="timeout",
                    ),
                    attempt=attempt,
                    http_session_id=http_session_id,
                    chat_session_id=chat_session_id,
                    tracked_attempt=tracked_attempt,
                ),
                exc,
            )
        finally:
            deadline.disarm()
            if query_operation is not None:
                await clear_query_operation_if_owned(query_operation, self._redis)
            await self._release_lock_if_owned(http_session_id, lock_owner)

    async def accept_query(
        self,
        http_session_id: str,
        user_id: str,
        attempt_id: str,
        chat_session_id: str | None = None,
    ) -> AcceptedQuerySummary:
        """Accept a query result: persist to DB and delete Redis attempt."""
        # Verify user exists in DB (guard against stale Redis sessions)
        user_uuid = uuid.UUID(user_id)
        user_result = await self._db_session.execute(select(User).where(User.id == user_uuid))
        user_row = user_result.scalar_one_or_none()
        if user_row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthorized", "message_key": "error.unauthorized"},
            )

        lock_key = f"accept:{attempt_id}"
        lock_acquired = await self._redis.set(lock_key, "1", nx=True, ex=5)
        if not lock_acquired:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "accept_conflict", "message_key": "error.acceptConflict"},
            )

        try:
            # G-004: verify this is the current active attempt for the session
            active_attempt_id = await self._redis.get(f"active_attempt:{http_session_id}")
            if active_attempt_id != attempt_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "attempt_not_active", "message_key": "error.attemptInvalid"},
                )

            try:
                attempt_obj = await get_attempt(attempt_id, http_session_id, user_id, self._redis)
                self._require_attempt_binding(attempt_obj, user_id)
            except AttemptNotFound:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "attempt_expired", "message_key": "error.attemptExpired"},
                ) from None
            except AttemptOwnershipViolation:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "attempt_invalid", "message_key": "error.attemptInvalid"},
                ) from None

            attempt = attempt_obj.model_dump()

            if attempt.get("state") != "EXECUTED":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "attempt_state_invalid", "message_key": "error.attemptStateInvalid"},
                )

            # Idempotency: skip if already persisted for this attempt_id (auto-saved)
            existing = await self._repo.get_by_attempt_id(attempt_id, user_uuid)
            if existing is not None:
                if existing.database_connection_id != attempt_obj.database_connection_id:
                    raise AttemptContextInvalid()
                await delete_attempt(attempt_id, self._redis)
                await self._redis.delete(f"active_attempt:{http_session_id}")
                # FR-140: emit query.accept even on the idempotent
                # path; the user made a distinct accept decision
                # (click). resource_id is the existing accepted
                # query id (audit standard); accepted_query_id is
                # NOT duplicated in context.
                await AuditService.log(
                    self._db_session,
                    action=AuditActionType.QUERY_ACCEPT,
                    actor_id=user_uuid,
                    actor_identity=getattr(user_row, "username", None),
                    resource_type="accepted_query",
                    resource_id=str(existing.id),
                    outcome="success",
                    context={},
                )
                return AcceptedQuerySummary(
                    id=str(existing.id),
                    question_text=existing.question_text,
                    generated_sql=existing.generated_sql,
                    accepted_at=existing.accepted_at.isoformat(),
                    database_connection_id=(
                        str(existing.database_connection_id) if existing.database_connection_id else None
                    ),
                )

            session_uuid = uuid.UUID(chat_session_id) if chat_session_id else None
            query = await self._repo.create(
                user_id=user_uuid,
                database_connection_id=attempt_obj.database_connection_id,
                question_text=attempt.get("question", ""),
                generated_sql=attempt.get("sql", ""),
                llm_provider=attempt.get("llm_provider", ""),
                attempt_id=attempt_id,
                session_id=session_uuid,
                saved=True,
                feedback=1,
            )

            await delete_attempt(attempt_id, self._redis)
            await self._redis.delete(f"active_attempt:{http_session_id}")

            # FR-140: emit query.accept on the fresh path.
            # resource_id is the freshly-created accepted query
            # id (audit standard; not a leak). accepted_query_id
            # is NOT duplicated in context. No SQL, no question
            # text, no row data in the context.
            await AuditService.log(
                self._db_session,
                action=AuditActionType.QUERY_ACCEPT,
                actor_id=user_uuid,
                actor_identity=getattr(user_row, "username", None),
                resource_type="accepted_query",
                resource_id=str(query.id),
                outcome="success",
                context={},
            )

            return AcceptedQuerySummary(
                id=str(query.id),
                question_text=query.question_text,
                generated_sql=query.generated_sql,
                accepted_at=query.accepted_at.isoformat(),
                database_connection_id=(str(query.database_connection_id) if query.database_connection_id else None),
            )
        finally:
            await self._redis.delete(lock_key)

    async def reject_query(
        self,
        attempt_id: str,
        http_session_id: str,
        user_id: str,
    ) -> QueryResult | RefinePrompt:
        """Record an explicit rejection and run the shared retry lifecycle."""
        return await self._retry_query(
            _RetryRequest(
                attempt_id=attempt_id,
                http_session_id=http_session_id,
                user_id=user_id,
                decision_action=AuditActionType.QUERY_REJECT,
            )
        )

    async def regenerate_query(
        self,
        attempt_id: str,
        http_session_id: str,
        user_id: str,
    ) -> QueryResult | RefinePrompt:
        """Run the shared retry lifecycle without a rejection decision event."""
        return await self._retry_query(
            _RetryRequest(
                attempt_id=attempt_id,
                http_session_id=http_session_id,
                user_id=user_id,
            )
        )

    async def _retry_query(
        self,
        request: _RetryRequest,
    ) -> QueryResult | RefinePrompt:
        """Run the ordered quota, provider, validation, source, and audit retry lifecycle."""
        attempt_id = request.attempt_id
        http_session_id = request.http_session_id
        user_id = request.user_id
        lock_owner = await self._acquire_lock(http_session_id, ttl=self._query_lock_ttl)
        if lock_owner is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "concurrent", "message_key": "error.concurrent"},
            )

        deadline = self._start_query_deadline()
        user_uuid = uuid.UUID(user_id)
        prior: EphemeralAttempt | None = None
        timeout_attempt: EphemeralAttempt | None = None
        query_operation: QueryOperation | None = None
        tracked_attempt: TrackedAttempt | None = None
        chat_session_id: str | None = None
        actor_identity: str | None = None
        timeout_audit = _ExecutionFailureAudit(
            action=AuditActionType.QUERY_SUBMIT,
            actor_id=user_uuid,
            resource_type="query_attempt",
            resource_id=attempt_id,
            reason="timeout",
        )
        try:
            # G-001+G-004: verify active attempt
            active_attempt_id = await self._redis.get(f"active_attempt:{http_session_id}")
            if active_attempt_id != attempt_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "attempt_not_active", "message_key": "error.attemptInvalid"},
                )
            deadline.ensure_active()

            prior = await get_attempt(attempt_id, http_session_id, user_id, self._redis)
            timeout_attempt = prior
            connection_id = self._require_attempt_binding(prior, user_id)
            if prior.state != "EXECUTED":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "attempt_state_invalid", "message_key": "error.attemptStateInvalid"},
                )
            chat_session_id = prior.chat_session_id
            if chat_session_id is None:
                raise AttemptContextInvalid()
            await self._ensure_operation_active(chat_session_id, deadline)
            query_operation = QueryOperation(
                session_id=chat_session_id,
                user_id=user_id,
                http_session_id=http_session_id,
                attempt_id=attempt_id,
                lock_owner=lock_owner,
                token=str(uuid.uuid4()),
            )
            if not await register_query_operation(query_operation, self._redis):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": "concurrent", "message_key": "error.concurrent"},
                )
            tracked_attempt = TrackedAttempt(
                session_id=chat_session_id,
                user_id=user_id,
                http_session_id=http_session_id,
                attempt_id=attempt_id,
            )
            await track_session_attempt(tracked_attempt, self._redis)
            await self._ensure_operation_active(chat_session_id, deadline)

            # Critical 2: verify user exists in DB before any writes
            user_result = await self._db_session.execute(select(User).where(User.id == user_uuid))
            user_row = user_result.scalar_one_or_none()
            if user_row is None:
                await self._redis.delete(f"active_attempt:{http_session_id}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error": "unauthorized", "message_key": "error.unauthorized"},
                )
            actor_identity = user_row.username
            await self._ensure_operation_active(chat_session_id, deadline)

            if request.decision_action is not None:
                await self._persist_retry_audit(
                    _RetryAuditEvent(
                        action=request.decision_action,
                        actor_id=user_uuid,
                        actor_identity=actor_identity,
                        attempt_id=attempt_id,
                        outcome="success",
                    )
                )
                await self._ensure_operation_active(chat_session_id, deadline)

            # Max retries: max_regenerate_attempts = regen clicks after original (default 3)
            next_attempt_number = (prior.attempt_number or 1) + 1
            max_regens = await self._get_max_regenerate_attempts()
            await self._ensure_operation_active(chat_session_id, deadline)
            if next_attempt_number > max_regens + 1:
                await self._redis.delete(f"active_attempt:{http_session_id}")
                return RefinePrompt(
                    message_key="query.refine.message",
                    should_refine=True,
                )

            # Resolve current policy for the immutable connection
            # captured by the prior attempt at submit time.
            role_policy = await self._resolve_role_policy(
                user_id,
                connection_id,
            )
            await self._ensure_operation_active(chat_session_id, deadline)
            if role_policy is not None and not role_policy.allowed_tables:
                await self._persist_retry_audit(
                    _RetryAuditEvent(
                        action=AuditActionType.ACCESS_DENIED,
                        actor_id=user_uuid,
                        actor_identity=actor_identity,
                        attempt_id=attempt_id,
                        outcome="denied",
                        context={"reason": "deny_all"},
                    )
                )
                await self._redis.delete(f"active_attempt:{http_session_id}")
                return self._role_auth_rejection()

            # Build negative context from prior attempt
            negative_examples = [prior.sql] if prior.sql else []

            # T-712: filter schema before LLM call so the
            # regenerate prompt also respects the role's policy.
            schema_for_prompt = self._policy_schema_for_prompt(
                role_policy,
                self._schema_context,
            )
            await self._ensure_operation_active(chat_session_id, deadline)
            retry_attempt_id = str(uuid.uuid4())
            timeout_attempt = EphemeralAttempt(
                attempt_id=retry_attempt_id,
                session_id=http_session_id,
                chat_session_id=chat_session_id,
                user_id=user_id,
                database_connection_id=prior.database_connection_id,
                question=prior.question,
                attempt_number=next_attempt_number,
                llm_provider=self._llm_provider,
            )
            timeout_audit = _ExecutionFailureAudit(
                action=AuditActionType.QUERY_SUBMIT,
                actor_id=user_uuid,
                actor_identity=actor_identity,
                resource_type="query_attempt",
                resource_id=retry_attempt_id,
                reason="timeout",
            )
            provider_timeout = deadline.remaining_seconds()
            await self._consume_retry_quota(user_row, "queries", chat_session_id, deadline)
            try:
                new_sql = await self._run_chat_session_stage(
                    chat_session_id,
                    user_id,
                    self._llm.generate_sql(
                        prior.question,
                        schema_for_prompt,
                        negative_examples=negative_examples,
                        target_dialect=self._target_dialect,
                        timeout=provider_timeout,
                    ),
                )
            except asyncio.CancelledError:
                await self._ensure_chat_session_active(chat_session_id)
                raise
            except LLMTimeout as exc:
                raise QueryDeadlineExpired() from exc
            except Exception:
                await self._ensure_operation_active(chat_session_id, deadline)
                await self._persist_retry_audit(
                    _RetryAuditEvent(
                        action=AuditActionType.QUERY_SUBMIT,
                        actor_id=user_uuid,
                        actor_identity=actor_identity,
                        attempt_id=retry_attempt_id,
                        outcome="failure",
                        context={"reason": "provider_failure"},
                    )
                )
                await self._redis.delete(f"active_attempt:{http_session_id}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"error": "llm_unavailable", "message_key": "error.llmUnavailable"},
                ) from None
            await self._ensure_operation_active(chat_session_id, deadline)
            await self._persist_retry_audit(
                _RetryAuditEvent(
                    action=AuditActionType.QUERY_SUBMIT,
                    actor_id=user_uuid,
                    actor_identity=actor_identity,
                    attempt_id=retry_attempt_id,
                    outcome="success",
                )
            )
            timeout_audit = _ExecutionFailureAudit(
                action=AuditActionType.QUERY_VALIDATE_FAIL,
                actor_id=user_uuid,
                actor_identity=actor_identity,
                resource_type="query_attempt",
                resource_id=retry_attempt_id,
                reason="timeout",
            )
            await self._ensure_operation_active(chat_session_id, deadline)

            # Inv 4: byte-equal duplicate detection
            if new_sql == prior.sql:
                await self._persist_retry_audit(
                    _RetryAuditEvent(
                        action=AuditActionType.QUERY_VALIDATE_FAIL,
                        actor_id=user_uuid,
                        actor_identity=actor_identity,
                        attempt_id=retry_attempt_id,
                        outcome="failure",
                        context={"reason": "duplicate_candidate"},
                    )
                )
                await delete_attempt(attempt_id, self._redis)
                await self._redis.delete(f"active_attempt:{http_session_id}")
                return RefinePrompt(
                    message_key="query.refine.message",
                    should_refine=True,
                )

            # Inv 1: evaluator gate
            try:
                eval_result = await self._run_chat_session_stage(
                    chat_session_id,
                    user_id,
                    self._evaluator.evaluate(new_sql, None),
                )
            except asyncio.CancelledError:
                await self._ensure_chat_session_active(chat_session_id)
                raise
            await self._ensure_operation_active(chat_session_id, deadline)
            if not eval_result.passed:
                await self._persist_retry_audit(
                    _RetryAuditEvent(
                        action=AuditActionType.QUERY_VALIDATE_FAIL,
                        actor_id=user_uuid,
                        actor_identity=actor_identity,
                        attempt_id=retry_attempt_id,
                        outcome="failure",
                        context={"reason": "evaluator_rejected"},
                    )
                )
                timeout_attempt, tracked_attempt = await self._store_rejected_retry(
                    _RejectedRetry(
                        prior_attempt_id=attempt_id,
                        retry_attempt_id=retry_attempt_id,
                        http_session_id=http_session_id,
                        chat_session_id=chat_session_id,
                        user_id=user_id,
                        database_connection_id=prior.database_connection_id,
                        sql=new_sql,
                        question=prior.question,
                        attempt_number=next_attempt_number,
                        violations=[
                            {"rule": violation.rule_name, "message_key": violation.message_key}
                            for violation in eval_result.violations
                        ],
                    ),
                    deadline,
                )
                return RefinePrompt(
                    message_key="query.refine.message",
                    should_refine=True,
                )

            await self._persist_retry_audit(
                _RetryAuditEvent(
                    action=AuditActionType.QUERY_VALIDATE_PASS,
                    actor_id=user_uuid,
                    actor_identity=actor_identity,
                    attempt_id=retry_attempt_id,
                    outcome="success",
                )
            )
            timeout_audit = _ExecutionFailureAudit(
                action=AuditActionType.QUERY_EXECUTE,
                actor_id=user_uuid,
                actor_identity=actor_identity,
                resource_type="query_attempt",
                resource_id=retry_attempt_id,
                reason="timeout",
            )
            await self._ensure_operation_active(chat_session_id, deadline)

            # T-712: policy-based role authorization on the
            # regenerated SQL. Returns a RefinePrompt (treating it
            # as a rejected regenerate) — the next click would be a
            # refine prompt anyway.
            role_auth_rejection = await self._enforce_role_authorization(new_sql, role_policy)
            await self._ensure_operation_active(chat_session_id, deadline)
            if role_auth_rejection is not None:
                await self._persist_retry_audit(
                    _RetryAuditEvent(
                        action=AuditActionType.ACCESS_DENIED,
                        actor_id=user_uuid,
                        actor_identity=actor_identity,
                        attempt_id=retry_attempt_id,
                        outcome="denied",
                        context={"reason": "role_authorization"},
                    )
                )
                timeout_attempt, tracked_attempt = await self._store_rejected_retry(
                    _RejectedRetry(
                        prior_attempt_id=attempt_id,
                        retry_attempt_id=retry_attempt_id,
                        http_session_id=http_session_id,
                        chat_session_id=chat_session_id,
                        user_id=user_id,
                        database_connection_id=prior.database_connection_id,
                        sql=new_sql,
                        question=prior.question,
                        attempt_number=next_attempt_number,
                        violations=[
                            {"rule": violation.rule, "message_key": violation.message_key}
                            for violation in role_auth_rejection.violations
                        ],
                    ),
                    deadline,
                )
                return RefinePrompt(
                    message_key="query.refine.message",
                    should_refine=True,
                )

            # T-712: Apply per-role row filters before execute.
            row_filter_params: tuple[Any, ...] = ()
            effective_sql = new_sql
            if role_policy is not None and role_policy.row_filters:
                try:
                    bound = self._policy.apply_row_filters(
                        sql=new_sql,
                        row_filters=role_policy.row_filters,
                        schema=self._schema_context
                        if isinstance(self._schema_context, SchemaContext)
                        else SchemaContext(tables=[]),
                        user_context=role_policy.user_context,
                        dialect=self._target_dialect or "postgres",
                    )
                except PolicySchemaConflictError as exc:
                    await self._persist_retry_audit(
                        _RetryAuditEvent(
                            action=AuditActionType.POLICY_SCHEMA_MISMATCH,
                            actor_id=user_uuid,
                            actor_identity=actor_identity,
                            attempt_id=retry_attempt_id,
                            outcome="failure",
                            context={"reason": "policy_schema_conflict"},
                        )
                    )
                    await delete_attempt(attempt_id, self._redis)
                    await self._redis.delete(f"active_attempt:{http_session_id}")
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={
                            "error": "policy_schema_conflict",
                            "message_key": "error.policySchemaConflict",
                        },
                    ) from exc
                effective_sql = bound.sql
                row_filter_params = bound.params
            await self._ensure_operation_active(chat_session_id, deadline)
            source_timeout = deadline.remaining_seconds()
            await self._consume_retry_quota(user_row, "executions", chat_session_id, deadline)
            try:
                if self._adapter is not None:
                    exec_result = await self._run_chat_session_stage(
                        chat_session_id,
                        user_id,
                        self._adapter.execute(
                            effective_sql,
                            row_filter_params,
                            timeout=source_timeout,
                        ),
                    )
                    columns, rows = exec_result.columns, exec_result.rows
                else:
                    columns, rows = await self._run_chat_session_stage(
                        chat_session_id,
                        user_id,
                        self._executor.execute(
                            effective_sql,
                            timeout=source_timeout,
                            params=row_filter_params,
                        ),
                    )
            except asyncio.CancelledError:
                await self._ensure_chat_session_active(chat_session_id)
                await self._redis.delete(f"active_attempt:{http_session_id}")
                raise
            except (TimeoutError, SourceDBTimeout) as exc:
                raise QueryDeadlineExpired() from exc
            except Exception as exc:
                failure_status, failure_detail, failure_reason = _source_failure_response(exc)
                await self._persist_execution_failure_audit(
                    _ExecutionFailureAudit(
                        action=AuditActionType.QUERY_EXECUTE,
                        actor_id=user_uuid,
                        actor_identity=actor_identity,
                        resource_type="query_attempt",
                        resource_id=retry_attempt_id,
                        reason=failure_reason,
                    )
                )
                await delete_attempt(attempt_id, self._redis)
                await self._redis.delete(f"active_attempt:{http_session_id}")
                raise HTTPException(
                    status_code=failure_status,
                    detail=failure_detail,
                ) from None
            await self._ensure_operation_active(chat_session_id, deadline)

            # Mask the source result before recording successful execution.
            new_attempt_id = retry_attempt_id
            column_metas = []
            for c in columns:
                if isinstance(c, dict):
                    column_metas.append(ColumnMeta(name=c["name"], type=c["type"]))
                else:
                    column_metas.append(ColumnMeta(name=c, type="text"))
            masked_result = QueryResult(
                kind="result",
                attempt_id=new_attempt_id,
                question=prior.question,
                generated_sql=new_sql,
                columns=column_metas,
                rows=rows,
                row_count=len(rows),
                attempt_number=next_attempt_number,
                is_last_auto_retry=next_attempt_number >= max_regens + 1,
            )
            if role_policy is not None and role_policy.column_masks:
                try:
                    masked_result = self._policy.apply_column_masks(
                        masked_result,
                        role_policy.column_masks,
                        dialect=self._target_dialect,
                    )
                except Exception:
                    await self._persist_execution_failure_audit(
                        _ExecutionFailureAudit(
                            action=AuditActionType.QUERY_EXECUTE,
                            actor_id=user_uuid,
                            actor_identity=actor_identity,
                            resource_type="query_attempt",
                            resource_id=retry_attempt_id,
                            reason="result_processing_failed",
                        )
                    )
                    await delete_attempt(attempt_id, self._redis)
                    await self._redis.delete(f"active_attempt:{http_session_id}")
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail={
                            "error": "source_db_execution_failed",
                            "message_key": "error.sourceDbExecutionFailed",
                        },
                    ) from None
                column_metas = list(masked_result.columns)
                rows = masked_result.rows
            result = masked_result
            await self._ensure_operation_active(chat_session_id, deadline)

            # Auto-save regenerated result (Option B: update prior saved row in-place)
            # High 3: instead of creating a duplicate row, update the prior saved row
            # with new SQL/results to avoid confusing duplicates in history.
            session_uuid = None
            try:
                prior_saved = await self._repo.get_by_attempt_id(prior.attempt_id, user_uuid)
                if prior_saved is None:
                    db_conn_id = await self._get_database_connection_id()
                    saved_query = await self._repo.create(
                        user_id=user_uuid,
                        database_connection_id=uuid.UUID(db_conn_id),
                        question_text=prior.question,
                        generated_sql=new_sql,
                        llm_provider=self._llm_provider,
                        attempt_id=new_attempt_id,
                        session_id=uuid.UUID(chat_session_id),
                        saved=True,
                        feedback=1,
                        result_columns=[column.model_dump() for column in column_metas],
                        result_rows=_sanitize_for_json(rows),
                        result_row_count=len(rows),
                    )
                    result.accepted_query_id = str(saved_query.id)
                else:
                    session_uuid = prior_saved.session_id
                    prior_saved.generated_sql = new_sql
                    prior_saved.attempt_id = new_attempt_id
                    prior_saved.result_columns = [column.model_dump() for column in column_metas]
                    prior_saved.result_rows = _sanitize_for_json(rows)
                    prior_saved.result_row_count = len(rows)
                    prior_saved.accepted_at = datetime.now(UTC)
                    await self._db_session.flush()
                    result.accepted_query_id = str(prior_saved.id)
                    if session_uuid is not None:
                        result.session_id = str(session_uuid)
            except Exception:
                await self._db_session.rollback()
                await self._persist_retry_audit(
                    _RetryAuditEvent(
                        action=AuditActionType.QUERY_EXECUTE,
                        actor_id=user_uuid,
                        actor_identity=actor_identity,
                        attempt_id=retry_attempt_id,
                        outcome="success",
                    )
                )
                raise

            await self._ensure_operation_active(chat_session_id, deadline)
            try:
                await self._persist_retry_audit(
                    _RetryAuditEvent(
                        action=AuditActionType.QUERY_EXECUTE,
                        actor_id=user_uuid,
                        actor_identity=actor_identity,
                        attempt_id=retry_attempt_id,
                        outcome="success",
                    )
                )
            except Exception:
                await self._db_session.rollback()
                raise
            await self._ensure_operation_active(chat_session_id, deadline)

            new_attempt = EphemeralAttempt(
                attempt_id=new_attempt_id,
                session_id=http_session_id,
                chat_session_id=chat_session_id,
                user_id=user_id,
                database_connection_id=prior.database_connection_id,
                sql=new_sql,
                question=prior.question,
                attempt_number=next_attempt_number,
                llm_provider=self._llm_provider,
                state="EXECUTED",
            )
            timeout_attempt = new_attempt
            tracked_attempt = TrackedAttempt(
                session_id=chat_session_id,
                user_id=user_id,
                http_session_id=http_session_id,
                attempt_id=new_attempt_id,
            )
            await track_session_attempt(tracked_attempt, self._redis)
            await self._ensure_operation_active(chat_session_id, deadline)
            await store_attempt(new_attempt, http_session_id, self._redis)
            await self._redis.set(f"active_attempt:{http_session_id}", new_attempt_id)
            await self._ensure_operation_active(chat_session_id, deadline)
            await delete_attempt(attempt_id, self._redis)
            return result
        except SessionInvalidated:
            await self._discard_invalidated_attempt(tracked_attempt)
            raise
        except (QueryDeadlineExpired, asyncio.CancelledError) as exc:
            if isinstance(exc, asyncio.CancelledError) and not deadline.cancelled_current_task:
                raise
            deadline.disarm()
            if timeout_audit.resource_id != attempt_id:
                await delete_attempt(attempt_id, self._redis)
            await self._raise_timeout(
                _TimeoutFailure(
                    audit=timeout_audit,
                    attempt=timeout_attempt,
                    http_session_id=http_session_id,
                    chat_session_id=chat_session_id,
                    tracked_attempt=tracked_attempt,
                ),
                exc,
            )
        finally:
            deadline.disarm()
            if query_operation is not None:
                await clear_query_operation_if_owned(query_operation, self._redis)
            await self._release_lock_if_owned(http_session_id, lock_owner)

    async def rerun_accepted_query(
        self,
        accepted_query_id: str,
        user_id: str,
        connection_id: str | None = None,
    ) -> QueryResult | EvaluatorRejection | None:
        """Re-execute accepted SQL within the configured operation deadline."""
        user_uuid = uuid.UUID(user_id)
        accepted_uuid = uuid.UUID(accepted_query_id)
        lock_session_id = f"rerun:{accepted_query_id}"
        lock_owner = await self._acquire_lock(lock_session_id, ttl=self._query_lock_ttl)
        if lock_owner is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "concurrent", "message_key": "error.concurrent"},
            )

        deadline = self._start_query_deadline()
        try:
            return await self._rerun_accepted_query_with_deadline(
                accepted_query_id,
                user_id,
                connection_id,
                deadline,
            )
        except (QueryDeadlineExpired, asyncio.CancelledError) as exc:
            if isinstance(exc, asyncio.CancelledError) and not deadline.cancelled_current_task:
                raise
            deadline.disarm()
            await self._raise_timeout(
                _TimeoutFailure(
                    audit=_ExecutionFailureAudit(
                        action=AuditActionType.QUERY_RERUN,
                        actor_id=user_uuid,
                        resource_type="accepted_query",
                        resource_id=str(accepted_uuid),
                        reason="timeout",
                    ),
                ),
                exc,
            )
        finally:
            deadline.disarm()
            await self._release_lock_if_owned(lock_session_id, lock_owner)

    async def _rerun_accepted_query_with_deadline(
        self,
        accepted_query_id: str,
        user_id: str,
        connection_id: str | None,
        deadline: QueryDeadline,
    ) -> QueryResult | EvaluatorRejection | None:
        """Re-execute a previously accepted query.

        Per FR-135. The stored SQL is re-validated against the
        user's CURRENT role policy before execution. If the role
        has been restricted since the query was accepted, the
        rerun is blocked with a sanitized ``EvaluatorRejection``
        (i18n key: ``error.queryBlockedPolicy``) before the
        executor is called. The historical role policy from
        acceptance time is NOT trusted; only the live provider
        is consulted.

        Per SC-053: the accepted query is scoped by the caller
        ``user_id`` at the repo ``WHERE`` clause. A cross-user
        or non-existent ``accepted_query_id`` returns ``None``
        so the caller can surface a sanitized 404. The LLM is
        never called for rerun. Accepted query rows are NOT
        mutated on the rerun path (read-only).

        Args:
            accepted_query_id: ID of the accepted query to rerun.
            user_id: The authenticated user's ID. Used to scope
                the repo lookup and resolve the current role
                policy.
            connection_id: Optional connection override; falls
                back to ``self._connection_id`` (request-scoped)
                then to the first configured source DB.

        Returns:
            ``QueryResult``: on successful re-execution.
            ``EvaluatorRejection``: if the current role policy
                blocks the stored SQL (sanitized; no table,
                column, SQL, UUID, user value, role id, or
                connection id leak).
            ``None``: if the accepted query is not found or
                belongs to a different user. Caller is
                responsible for translating to a sanitized 404.

        Raises:
            HTTPException 409: row filter references a column
                that was removed by schema drift
                (``error.policySchemaConflict``).
            HTTPException 504: source DB execution timed out
                (``error.timeout``).
        """
        user_uuid = uuid.UUID(user_id)
        aq_uuid = uuid.UUID(accepted_query_id)
        accepted = await self._repo.get_by_id(aq_uuid, user_uuid)
        deadline.ensure_active()
        if accepted is None:
            return None

        # Multi-connection fix: the accepted row's
        # ``database_connection_id`` is the AUTHORITATIVE
        # connection for policy resolution AND execution.
        # The rerun runs through the already-built service
        # context (``self._adapter`` / ``self._executor`` /
        # ``self._schema_context`` / ``self._target_dialect``),
        # so the service's ``self._connection_id`` (when set)
        # MUST also match the accepted row's id. Two checks:
        #
        # 1. Service context: if the service was built for a
        #    specific connection (request-scoped), it must
        #    match the accepted row's connection. Otherwise
        #    we'd authorize with A's policy and execute under
        #    C's adapter / schema / dialect / executor — a
        #    multi-connection leak.
        # 2. Caller-supplied connection_id (cross-check): if
        #    the caller passed a connection_id and it differs
        #    from the accepted row's id, the rerun is
        #    rejected before any DB or policy work.
        #
        # If ``self._connection_id`` is ``None`` the service
        # is unscoped (legacy / single-connection build); the
        # caller-supplied check still applies.
        if (
            self._connection_id is not None
            and accepted.database_connection_id is not None
            and self._connection_id != str(accepted.database_connection_id)
        ):
            return None
        if (
            connection_id is not None
            and accepted.database_connection_id is not None
            and connection_id != str(accepted.database_connection_id)
        ):
            return None

        stored_sql = accepted.generated_sql
        if not stored_sql:
            return self._role_auth_rejection()

        # Use the accepted row's connection id (not the
        # caller's arg, not the service default, not the
        # first configured source DB) for policy resolution.
        resolved_connection_id = (
            str(accepted.database_connection_id) if accepted.database_connection_id is not None else connection_id
        )
        role_policy = await self._resolve_role_policy(user_id, resolved_connection_id)
        deadline.ensure_active()

        if role_policy is not None and not role_policy.allowed_tables:
            return self._role_auth_rejection()

        rejection = await self._enforce_role_authorization(stored_sql, role_policy)
        deadline.ensure_active()
        if rejection is not None:
            return rejection

        row_filter_params: tuple[Any, ...] = ()
        effective_sql = stored_sql
        if role_policy is not None and role_policy.row_filters:
            try:
                bound = self._policy.apply_row_filters(
                    sql=stored_sql,
                    row_filters=role_policy.row_filters,
                    schema=self._schema_context
                    if isinstance(self._schema_context, SchemaContext)
                    else SchemaContext(tables=[]),
                    user_context=role_policy.user_context,
                    dialect=self._target_dialect or "postgres",
                )
            except PolicySchemaConflictError as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "policy_schema_conflict",
                        "message_key": "error.policySchemaConflict",
                    },
                ) from exc
            effective_sql = bound.sql
            row_filter_params = bound.params
        deadline.ensure_active()

        try:
            source_timeout = deadline.remaining_seconds()
            if self._adapter is not None:
                exec_result = await self._adapter.execute(
                    effective_sql,
                    row_filter_params,
                    timeout=source_timeout,
                )
                columns, rows = exec_result.columns, exec_result.rows
            else:
                columns, rows = await self._executor.execute(
                    effective_sql,
                    timeout=source_timeout,
                    params=row_filter_params,
                )
        except (TimeoutError, SourceDBTimeout) as exc:
            raise QueryDeadlineExpired() from exc
        except Exception as exc:
            failure_status, failure_detail, failure_reason = _source_failure_response(exc)
            await self._persist_execution_failure_audit(
                _ExecutionFailureAudit(
                    action=AuditActionType.QUERY_RERUN,
                    actor_id=user_uuid,
                    resource_type="accepted_query",
                    resource_id=str(aq_uuid),
                    reason=failure_reason,
                )
            )
            raise HTTPException(
                status_code=failure_status,
                detail=failure_detail,
            ) from None
        deadline.ensure_active()

        column_metas = []
        for c in columns:
            if isinstance(c, dict):
                column_metas.append(ColumnMeta(name=c["name"], type=c["type"]))
            else:
                column_metas.append(ColumnMeta(name=c, type="text"))
        masked_result = QueryResult(
            kind="result",
            attempt_id=f"rerun-{accepted_query_id}",
            session_id=str(accepted.session_id) if accepted.session_id else None,
            question=accepted.question_text,
            generated_sql=stored_sql,
            columns=column_metas,
            rows=rows,
            row_count=len(rows),
            attempt_number=1,
            is_last_auto_retry=False,
            accepted_query_id=str(aq_uuid),
        )
        if role_policy is not None and role_policy.column_masks:
            masked_result = self._policy.apply_column_masks(
                masked_result,
                role_policy.column_masks,
                dialect=self._target_dialect,
            )
        deadline.ensure_active()

        await AuditService.log(
            self._db_session,
            action=AuditActionType.QUERY_RERUN,
            actor_id=user_uuid,
            resource_type="accepted_query",
            resource_id=str(aq_uuid),
            outcome="success",
            context={},
        )
        deadline.ensure_active()

        return masked_result
