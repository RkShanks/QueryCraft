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
from typing import Any

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.attempt_store import EphemeralAttempt, delete_attempt, get_attempt, store_attempt
from app.core.exceptions import (
    AttemptNotFound,
    AttemptOwnershipViolation,
    PolicySchemaConflictError,
    SourceDBTimeout,
)
from app.core.processing_lock import acquire_lock, release_lock_if_owned
from app.db.models.user import User
from app.evaluator.rules.role_authorization import RoleAuthorizationRule
from app.evaluator.schema_context import SchemaContext
from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.query import (
    AcceptedQuerySummary,
    ColumnMeta,
    EvaluatorRejection,
    QueryResult,
    RefinePrompt,
    Violation,
)
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

    async def _acquire_lock(self, session_id: str, ttl: int = 60) -> str | None:
        """Try to acquire a per-session processing lock.

        Returns an owner token (uuid string) if acquired, None if already held.
        """
        return await acquire_lock(session_id, self._redis, ttl=ttl)

    async def _release_lock_if_owned(self, session_id: str, owner: str | None) -> bool:
        """Release the processing lock only if we own it."""
        return await release_lock_if_owned(session_id, owner, self._redis)

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
        """Return the source_database_connection id.

        Uses the connection-scoped ID when available (Phase 3 multi-connection).
        Falls back to first source_database_connection id (Phase 1: single DB).

        Raises:
            HTTPException 500 if no source_database_connections row exists.
        """
        if self._connection_id is not None:
            return self._connection_id
        result = await self._db_session.execute(text("SELECT id FROM source_database_connections LIMIT 1"))
        row = result.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "config_error",
                    "message_key": "error.sourceDbNotConfigured",
                },
            )
        return str(row[0])

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
        lock_owner = await self._acquire_lock(http_session_id, ttl=300)
        if lock_owner is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "concurrent", "message_key": "error.concurrent"},
            )

        try:
            user_uuid = uuid.UUID(user_id)

            # Verify user exists in DB (guard against stale Redis sessions)
            result = await self._db_session.execute(select(User).where(User.id == user_uuid))
            user_row = result.scalar_one_or_none()
            if user_row is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error": "unauthorized", "message_key": "error.unauthorized"},
                )

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

            attempt_id = str(uuid.uuid4())
            attempt = EphemeralAttempt(
                attempt_id=attempt_id,
                session_id=http_session_id,
                user_id=user_id,
                question=question,
                state="PENDING",
                llm_provider=self._llm_provider,
            )

            await store_attempt(attempt, http_session_id, self._redis)

            # T-712: Resolve role policy. When the user has a role_id
            # and a connection-scoped policy exists, the LLM prompt
            # is filtered to role-allowed schema and a
            # ``RoleAuthorizationRule`` is added to the evaluator
            # pipeline. When the user has no role_id (Phase 1-3
            # backwards compat) the provider returns ``None`` and
            # every policy step is a no-op.
            role_policy = await self._resolve_role_policy(
                user_id,
                connection_id,
            )
            if role_policy is not None and not role_policy.allowed_tables:
                # Deny-all policy: fail closed before the LLM so the
                # user never gets a prompt that mentions any table.
                attempt.state = "REJECTED"
                attempt.evaluator_result = {
                    "passed": False,
                    "violations": [{"rule": "role_authorization", "message_key": "error.queryBlockedPolicy"}],
                }
                await store_attempt(attempt, http_session_id, self._redis)
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
            try:
                sql = await self._llm.generate_sql(
                    question=question,
                    schema_context=schema_for_prompt,
                    conversation_history=conversation_history or None,
                    target_dialect=self._target_dialect,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"error": "llm_unavailable", "message_key": "error.llmUnavailable"},
                ) from exc

            attempt.sql = sql
            attempt.state = "GENERATED"
            await store_attempt(attempt, http_session_id, self._redis)

            # 2. Evaluator gate (existing rules)
            eval_result = await self._evaluator.evaluate(sql, None)
            if not eval_result.passed:
                attempt.state = "REJECTED"
                attempt.evaluator_result = {
                    "passed": False,
                    "violations": [{"rule": v.rule_name, "message_key": v.message_key} for v in eval_result.violations],
                }
                await store_attempt(attempt, http_session_id, self._redis)
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
            role_auth_rejection = await self._enforce_role_authorization(sql, role_policy)
            if role_auth_rejection is not None:
                attempt.state = "REJECTED"
                attempt.evaluator_result = {
                    "passed": False,
                    "violations": [
                        {"rule": v.rule, "message_key": v.message_key} for v in role_auth_rejection.violations
                    ],
                }
                await store_attempt(attempt, http_session_id, self._redis)
                return role_auth_rejection

            attempt.state = "EVALUATED"
            await store_attempt(attempt, http_session_id, self._redis)

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

            # 4. Execute against source DB. Adapter and legacy
            # executor both receive the rewritten SQL + row-filter
            # params. asyncpg positional binding is used; the
            # adapter's ``execute(sql, params)`` signature accepts
            # the tuple unchanged.
            try:
                if self._adapter is not None:
                    exec_result = await asyncio.wait_for(
                        self._adapter.execute(effective_sql, row_filter_params),
                        timeout=30,
                    )
                    columns, rows = exec_result.columns, exec_result.rows
                else:
                    columns, rows = await asyncio.wait_for(
                        self._executor.execute(effective_sql, timeout=30, params=row_filter_params),
                        timeout=30,
                    )
            except (TimeoutError, SourceDBTimeout) as exc:
                attempt.state = "TIMEOUT"
                await store_attempt(attempt, http_session_id, self._redis)
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail={"error": "timeout", "message_key": "error.timeout"},
                ) from exc

            attempt.state = "EXECUTED"
            attempt.executor_result = {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }
            await store_attempt(attempt, http_session_id, self._redis)

            # 4a. T-712: Apply per-role column masks to the
            # ``QueryResult`` after execution. Returns a new
            # ``QueryResult`` with masked values (``"***"``) and
            # ``ColumnMeta.masked = True``. When no policy applies
            # this is a no-op that returns an original-equivalent
            # ``QueryResult`` (input not mutated). The masked rows
            # are what get persisted to the accepted-query history
            # — unmasked sensitive values never touch the response
            # or the DB.
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
                )
                # Refresh ColumnMeta list from the masked result so
                # the masked flags are reflected in the response.
                column_metas = list(masked_result.columns)
                rows = masked_result.rows
            result = masked_result

            # 5. Auto-save (idempotent: skip if already persisted for this attempt_id)
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

            # Track active attempt for session (G-001+G-004)
            await self._redis.set(f"active_attempt:{http_session_id}", attempt_id)

            return result
        finally:
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
        if user_result.scalar_one_or_none() is None:
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
                attempt_obj = await get_attempt(attempt_id, http_session_id, self._redis)
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
                await delete_attempt(attempt_id, self._redis)
                await self._redis.delete(f"active_attempt:{http_session_id}")
                return AcceptedQuerySummary(
                    id=str(existing.id),
                    question_text=existing.question_text,
                    generated_sql=existing.generated_sql,
                    accepted_at=existing.accepted_at.isoformat(),
                    database_connection_id=(
                        str(existing.database_connection_id) if existing.database_connection_id else None
                    ),
                )

            # Resolve database_connection_id internally (High 2 fix)
            db_conn_id = await self._get_database_connection_id()
            session_uuid = uuid.UUID(chat_session_id) if chat_session_id else None
            query = await self._repo.create(
                user_id=user_uuid,
                database_connection_id=uuid.UUID(db_conn_id),
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
    ) -> QueryResult | RefinePrompt:
        """Reject a query result and trigger one auto-retry.

        Behaviour is identical to regenerate_query: discards the current
        attempt, provides it as negative context to the LLM, and generates
        a new SQL attempt. If this is the second consecutive rejection (or
        the regenerated SQL is byte-equal), returns a RefinePrompt instead
        of a new result.

        Raises:
            SessionBusy: if a concurrent operation is in progress.
            AttemptNotFound: if the attempt does not exist.
            AttemptOwnershipViolation: if session_id doesn't match.
        """
        return await self.regenerate_query(attempt_id, http_session_id)

    async def regenerate_query(
        self,
        attempt_id: str,
        http_session_id: str,
    ) -> QueryResult | RefinePrompt:
        """Regenerate SQL for a rejected query result.

        Flow:
        1. Acquire processing lock (Critical 1 fix).
        2. Verify user exists in DB (Critical 2 fix).
        3. Get prior attempt (validate ownership).
        4. Build LLM prompt with negative context.
        5. Call LLM.
        6. Inv 4 byte-equal check.
        7. Run evaluator (Inv 1).
        8. Run executor.
        9. Auto-save: update prior row in-place (Option B, High 3 fix).
        10. Release lock, return QueryResult.

        Raises:
            HTTPException 409: if another operation holds the session processing lock.
            HTTPException 401: if the user has been deleted from DB.
        """
        lock_owner = await self._acquire_lock(http_session_id, ttl=300)
        if lock_owner is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "concurrent", "message_key": "error.concurrent"},
            )

        try:
            # G-001+G-004: verify active attempt
            active_attempt_id = await self._redis.get(f"active_attempt:{http_session_id}")
            if active_attempt_id != attempt_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "attempt_not_active", "message_key": "error.attemptInvalid"},
                )

            prior = await get_attempt(attempt_id, http_session_id, self._redis)
            await delete_attempt(attempt_id, self._redis)

            # Critical 2: verify user exists in DB before any writes
            user_uuid = uuid.UUID(prior.user_id) if prior.user_id else None
            if user_uuid is not None:
                user_result = await self._db_session.execute(select(User).where(User.id == user_uuid))
                if user_result.scalar_one_or_none() is None:
                    await self._redis.delete(f"active_attempt:{http_session_id}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail={"error": "unauthorized", "message_key": "error.unauthorized"},
                    )

            # Max retries: max_regenerate_attempts = regen clicks after original (default 3)
            next_attempt_number = (prior.attempt_number or 1) + 1
            max_regens = await self._get_max_regenerate_attempts()
            if next_attempt_number > max_regens + 1:
                await self._redis.delete(f"active_attempt:{http_session_id}")
                return RefinePrompt(
                    message_key="query.refine.message",
                    should_refine=True,
                )

            # T-712: Resolve role policy for the connection this
            # regenerate is operating on. Falls back to
            # ``self._connection_id`` (constructor-set) since
            # ``regenerate_query`` does not take a request-supplied
            # ``connection_id`` — it operates on a prior attempt
            # whose connection is whatever was active at submit time.
            role_policy = await self._resolve_role_policy(
                prior.user_id or "",
                self._connection_id,
            )
            if role_policy is not None and not role_policy.allowed_tables:
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

            # Call LLM
            try:
                new_sql = await self._llm.generate_sql(
                    prior.question,
                    schema_for_prompt,
                    negative_examples=negative_examples,
                )
            except Exception as exc:
                await self._redis.delete(f"active_attempt:{http_session_id}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"error": "llm_unavailable", "message_key": "error.llmUnavailable"},
                ) from exc

            # Inv 4: byte-equal duplicate detection
            if new_sql == prior.sql:
                await self._redis.delete(f"active_attempt:{http_session_id}")
                return RefinePrompt(
                    message_key="query.refine.message",
                    should_refine=True,
                )

            # Inv 1: evaluator gate
            eval_result = await self._evaluator.evaluate(new_sql, None)
            if not eval_result.passed:
                new_attempt_id = str(uuid.uuid4())
                failed_attempt = EphemeralAttempt(
                    attempt_id=new_attempt_id,
                    session_id=http_session_id,
                    sql=new_sql,
                    question=prior.question,
                    attempt_number=next_attempt_number,
                    llm_provider=self._llm_provider,
                    evaluator_result={
                        "passed": False,
                        "violations": [
                            {"rule": v.rule_name, "message_key": v.message_key} for v in eval_result.violations
                        ],
                    },
                )
                await store_attempt(failed_attempt, http_session_id, self._redis)
                await self._redis.delete(f"active_attempt:{http_session_id}")
                return RefinePrompt(
                    message_key="query.refine.message",
                    should_refine=True,
                )

            # T-712: policy-based role authorization on the
            # regenerated SQL. Returns a RefinePrompt (treating it
            # as a rejected regenerate) — the next click would be a
            # refine prompt anyway.
            role_auth_rejection = await self._enforce_role_authorization(new_sql, role_policy)
            if role_auth_rejection is not None:
                new_attempt_id = str(uuid.uuid4())
                failed_attempt = EphemeralAttempt(
                    attempt_id=new_attempt_id,
                    session_id=http_session_id,
                    sql=new_sql,
                    question=prior.question,
                    attempt_number=next_attempt_number,
                    llm_provider=self._llm_provider,
                    evaluator_result={
                        "passed": False,
                        "violations": [
                            {"rule": v.rule, "message_key": v.message_key} for v in role_auth_rejection.violations
                        ],
                    },
                )
                await store_attempt(failed_attempt, http_session_id, self._redis)
                await self._redis.delete(f"active_attempt:{http_session_id}")
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

            # Execute against source DB
            try:
                if self._adapter is not None:
                    exec_result = await asyncio.wait_for(
                        self._adapter.execute(effective_sql, row_filter_params),
                        timeout=30,
                    )
                    columns, rows = exec_result.columns, exec_result.rows
                else:
                    columns, rows = await asyncio.wait_for(
                        self._executor.execute(effective_sql, timeout=30, params=row_filter_params),
                        timeout=30,
                    )
            except (TimeoutError, SourceDBTimeout) as exc:
                await self._redis.delete(f"active_attempt:{http_session_id}")
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail={"error": "timeout", "message_key": "error.timeout"},
                ) from exc

            # Build result and store ephemeral attempt
            new_attempt_id = str(uuid.uuid4())
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
                masked_result = self._policy.apply_column_masks(
                    masked_result,
                    role_policy.column_masks,
                )
                column_metas = list(masked_result.columns)
                rows = masked_result.rows
            result = masked_result

            new_attempt = EphemeralAttempt(
                attempt_id=new_attempt_id,
                session_id=http_session_id,
                user_id=prior.user_id,
                sql=new_sql,
                question=prior.question,
                attempt_number=next_attempt_number,
                llm_provider=self._llm_provider,
                state="EXECUTED",
                executor_result={
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                },
            )
            await store_attempt(new_attempt, http_session_id, self._redis)
            await self._redis.set(f"active_attempt:{http_session_id}", new_attempt_id)

            # Auto-save regenerated result (Option B: update prior saved row in-place)
            # High 3: instead of creating a duplicate row, update the prior saved row
            # with new SQL/results to avoid confusing duplicates in history.
            session_uuid = None
            if user_uuid is not None:
                prior_saved = await self._repo.get_by_attempt_id(prior.attempt_id, user_uuid)
                if prior_saved is not None:
                    session_uuid = prior_saved.session_id
                    # Update in-place: replace SQL, results, and attempt_id
                    prior_saved.generated_sql = new_sql
                    prior_saved.attempt_id = new_attempt_id
                    prior_saved.result_columns = [c.model_dump() for c in column_metas]
                    prior_saved.result_rows = _sanitize_for_json(rows)
                    prior_saved.result_row_count = len(rows)
                    prior_saved.accepted_at = datetime.now(UTC)
                    await self._db_session.flush()
                    result.accepted_query_id = str(prior_saved.id)
                else:
                    # No prior row — create fresh
                    db_conn_id = await self._get_database_connection_id()
                    saved_query = await self._repo.create(
                        user_id=user_uuid,
                        database_connection_id=uuid.UUID(db_conn_id),
                        question_text=prior.question,
                        generated_sql=new_sql,
                        llm_provider=self._llm_provider,
                        attempt_id=new_attempt_id,
                        session_id=None,
                        saved=True,
                        feedback=1,
                        result_columns=[c.model_dump() for c in column_metas],
                        result_rows=_sanitize_for_json(rows),
                        result_row_count=len(rows),
                    )
                    result.accepted_query_id = str(saved_query.id)
                if session_uuid is not None:
                    result.session_id = str(session_uuid)

            return result
        finally:
            await self._release_lock_if_owned(http_session_id, lock_owner)
