"""T-717 — Accepted-query rerun re-validation tests.

Per FR-135 / SC-053. The rerun path re-validates a previously
accepted query against the user's CURRENT role policy. The
historical role policy from acceptance time is NOT trusted.

The rerun path:
  1. Loads the accepted query (scoped by user via
     ``AcceptedQueryRepository.get_by_id(query_id, user_id)``).
     Cross-user or non-existent ids return ``None`` so the caller
     can surface a sanitized 404.
  2. Resolves the user's CURRENT role policy for the connection
     via the configured ``role_policy_provider`` (or the real
     production provider for fail-closed coverage).
  3. Runs the ``RoleAuthorizationRule`` against the stored SQL.
  4. On policy block: returns a sanitized ``EvaluatorRejection``
     with i18n key ``error.queryBlockedPolicy``. The executor is
     NEVER called. No SQL, table, column, schema, UUID, user
     value, role id, connection id, DB error, host/port,
     username, credential, or token leaks in the response.
  5. On allow: applies per-role row filters (or no-op when no
     policy), executes the stored SQL against the source DB
     exactly once, then applies per-role column masks to the
     result. The accepted query row is NOT mutated.

Sanitization invariants (defence in depth):
  - The historical role policy is never trusted; only the live
    provider is consulted.
  - Missing policy row for a role-bearing user fails closed with
    ``error.queryBlockedPolicy`` (consistent with PR #129).
  - The ``role_id=None`` legacy path returns ``None`` from the
    provider; the rerun then executes without policy enforcement,
    preserving the Phase 1-3 contract.
  - The executor is called at most once per rerun.
  - The LLM is never called for rerun.
  - Accepted query records are not mutated on the rerun path.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.query import EvaluatorRejection, QueryResult
from app.services.query_service import QueryService

# ─── helpers ─────────────────────────────────────────────────────────


# i18n keys that must never appear in any rerun response.
# Mirrors the History TestSENSITIVE_TOKENS / sanitization pattern
# from Wave 17.3h.
_RERUN_FORBIDDEN_IN_RESPONSE = (
    "Traceback",
    "File ",
    "Error",
    "Exception",
    "asyncpg",
    "asyncio",
    "sqlalchemy",
    "10.0.0.42",
    "5432",
    "svc-prod",
    "***MASKED***",
    "ssn",
    "orders.ssn",
    "payments.ssn",
    "550e8400-e29b-41d4-a716-446655440000",
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002",
    "660e8400-e29b-41d4-a716-446655440000",
    "770e8400-e29b-41d4-a716-446655440000",
    "alice@example.com",
    "bob@example.com",
    "bob_smith",
    "admin_pw",
    "secret-token",
    "saml-xml",
)


@dataclass
class _RolePolicy:
    """Resolved role policy for a (user, connection) pair."""

    user_id: uuid.UUID
    role_id: uuid.UUID
    connection_id: uuid.UUID
    allowed_tables: list[dict] = field(default_factory=list)
    row_filters: list[dict] = field(default_factory=list)
    column_masks: list[dict] = field(default_factory=list)
    user_context: dict[str, Any] = field(default_factory=dict)


def _schema_context() -> MagicMock:
    """SchemaContext double with two tables: orders, payments."""
    from app.evaluator.schema_context import Column, SchemaContext, Table

    return SchemaContext(
        tables=[
            Table(
                name="orders",
                columns=[
                    Column(name="id", type="integer"),
                    Column(name="customer_id", type="integer"),
                    Column(name="ssn", type="text"),
                ],
            ),
            Table(
                name="payments",
                columns=[
                    Column(name="id", type="integer"),
                    Column(name="order_id", type="integer"),
                ],
            ),
        ]
    )


class _RecordingExecutor:
    """Records every execute call. Returns canned columns/rows."""

    def __init__(self, columns=None, rows=None):
        self._columns = columns or ["id"]
        self._rows = rows or [[1]]
        self.calls: list[dict] = []

    async def execute(self, sql, *args, **kwargs):
        params = kwargs.get("params", ())
        if not params and args:
            params = args[0] if isinstance(args[0], tuple) else args
        self.calls.append({"sql": sql, "params": params})
        return (self._columns, self._rows)


def _make_accepted_query(
    *,
    accepted_query_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    generated_sql: str = "SELECT orders.id FROM orders",
    question_text: str = "How many orders?",
    session_id: uuid.UUID | None = None,
) -> MagicMock:
    """Build an AcceptedQuery-like mock that the rerun path can read."""
    aq = MagicMock()
    aq.id = accepted_query_id or uuid.uuid4()
    aq.user_id = user_id or uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
    aq.generated_sql = generated_sql
    aq.question_text = question_text
    aq.session_id = session_id
    aq.database_connection_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
    return aq


def _make_rerun_service(
    *,
    accepted_query: MagicMock | None,
    policy_provider=None,
    executor: Any | None = None,
    apply_row_filters=None,
    apply_column_masks=None,
    user_id: str = "550e8400-e29b-41d4-a716-446655440000",
    role_id: str = "660e8400-e29b-41d4-a716-446655440000",
    connection_id: str = "770e8400-e29b-41d4-a716-446655440000",
) -> tuple[QueryService, dict]:
    """Build a QueryService with a stubbed accepted-query repo and a
    recording executor. Returns ``(service, deps)`` for inspection.

    The accepted-query repo's ``get_by_id`` is wired to return the
    supplied ``accepted_query`` (or ``None`` for the cross-user case).
    All other repo methods are stubbed to safe defaults.
    """
    user_uuid = uuid.UUID(user_id)
    role_uuid = uuid.UUID(role_id)
    conn_uuid = uuid.UUID(connection_id)

    db = MagicMock()
    db.flush = AsyncMock()

    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=accepted_query)
    repo.get_by_attempt_id = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=MagicMock(id="aaaaaaaa-0000-0000-0000-000000000001"))
    repo.update_feedback = AsyncMock(return_value=accepted_query)
    repo.delete_by_id = AsyncMock(return_value=True)
    repo.list_by_session = AsyncMock(return_value=[])
    repo.list_by_user = AsyncMock(return_value=([], None))
    repo.count_by_user = AsyncMock(return_value=0)
    repo.get_latest_by_session = AsyncMock(return_value=None)

    session_repo = MagicMock()
    session_repo.create = AsyncMock(return_value=MagicMock(id="550e8400-e29b-41d4-a716-446655440001"))
    session_repo.get_by_id = AsyncMock(return_value=None)
    session_repo.update_last_activity = AsyncMock(return_value=True)
    session_repo.update_preview_text = AsyncMock(return_value=True)

    class _FakeRedis:
        def __init__(self):
            self._data: dict[str, str] = {}

        async def set(self, key, value, nx=False, ex=None):
            if nx and key in self._data:
                return False
            self._data[key] = str(value)
            return True

        async def get(self, key):
            return self._data.get(key)

        async def delete(self, key):
            self._data.pop(key, None)
            return True

        async def eval(self, *a, **k):
            return 1

    actual_executor = executor or _RecordingExecutor()
    actual_policy_provider = policy_provider

    service = QueryService(
        accepted_query_repository=repo,
        session_repository=session_repo,
        db_session=db,
        redis=_FakeRedis(),
        # Rerun never calls the LLM. MagicMock is fine; the
        # implementation must not invoke it.
        llm=MagicMock(),
        evaluator=MagicMock(),
        source_db_executor=actual_executor,
        schema_context=_schema_context(),
        llm_provider="stub",
        connection_id=connection_id,
        target_dialect="postgres",
        role_policy_provider=actual_policy_provider,
    )

    # Optional: override the policy enforcement service so the rerun
    # path's row-filter + column-mask calls are stubbed. Tests that
    # need the real enforcement should pass None (default).
    if apply_row_filters is not None or apply_column_masks is not None:
        pol = MagicMock()
        if apply_row_filters is not None:
            pol.apply_row_filters = apply_row_filters
        if apply_column_masks is not None:
            pol.apply_column_masks = apply_column_masks
        service._policy = pol

    return service, {
        "repo": repo,
        "session_repo": session_repo,
        "db": db,
        "executor": actual_executor,
        "user_id": user_id,
        "user_uuid": user_uuid,
        "role_id": role_id,
        "role_uuid": role_uuid,
        "connection_id": connection_id,
        "conn_uuid": conn_uuid,
    }


# ─── 1. Happy path: allowed policy permits rerun ────────────────────


class TestRerunHappyPath:
    """Allowed current role policy permits rerun. Executor called
    exactly once with the stored SQL. No LLM call. No mutation of
    the accepted query row."""

    @pytest.mark.asyncio
    async def test_allowed_rerun_reaches_executor_exactly_once(self):
        """The stored SQL is re-validated against a policy that
        allows the referenced table. The rerun path returns a
        ``QueryResult``; the executor is called exactly once with
        the stored SQL; the LLM is never called; no mutation of
        the accepted query row."""
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        user_uuid = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        role_uuid = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")
        aq_id = uuid.UUID("aaaaaaaa-1111-1111-1111-000000000001")

        # Allowed policy: orders + payments, no row filters, no masks.
        policy = _RolePolicy(
            user_id=user_uuid,
            role_id=role_uuid,
            connection_id=conn_id,
            allowed_tables=[
                {"table": "orders", "columns": ["id", "customer_id", "ssn"]},
                {"table": "payments", "columns": ["id", "order_id"]},
            ],
        )

        async def _provider(uid, cid):
            return policy

        accepted = _make_accepted_query(
            accepted_query_id=aq_id,
            user_id=user_uuid,
            generated_sql="SELECT orders.id FROM orders",
        )
        service, deps = _make_rerun_service(
            accepted_query=accepted,
            policy_provider=_provider,
        )
        llm = service._llm

        result = await service.rerun_accepted_query(
            accepted_query_id=str(aq_id),
            user_id=str(user_uuid),
            connection_id=str(conn_id),
        )

        # Returned a QueryResult (not a rejection, not None).
        assert isinstance(result, QueryResult), f"expected QueryResult, got {type(result).__name__}: {result!r}"
        # Executor called exactly once with the stored SQL.
        assert len(deps["executor"].calls) == 1, (
            f"expected executor called exactly once, got {len(deps['executor'].calls)}: {deps['executor'].calls!r}"
        )
        assert deps["executor"].calls[0]["sql"] == "SELECT orders.id FROM orders"
        # LLM never called.
        llm.generate_sql.assert_not_called() if hasattr(llm, "generate_sql") else None
        # Accepted query row not mutated: no create / update / delete.
        deps["repo"].create.assert_not_called()
        deps["repo"].update_feedback.assert_not_called()
        deps["repo"].delete_by_id.assert_not_called()


# ─── 2. Restricted role policy blocks rerun ─────────────────────────


class TestRerunBlockedByRestrictedPolicy:
    """Restricted current role policy blocks rerun before executor.
    The block surfaces a sanitized ``EvaluatorRejection`` with i18n
    key ``error.queryBlockedPolicy``. No SQL, table, column, schema,
    UUID, user value, role id, connection id, DB error, or
    credential leaks in the rejection payload."""

    @pytest.mark.asyncio
    async def test_rerun_blocked_when_table_removed_from_policy(self):
        """User originally accepted a query against an unrestricted
        policy that allowed ``orders``. The role has since been
        restricted to ``payments`` only. Rerunning the accepted
        orders-query must be blocked with
        ``error.queryBlockedPolicy`` before the executor is called.
        No raw SQL, table, column, UUID, or user value leaks."""
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        user_uuid = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        role_uuid = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")
        aq_id = uuid.UUID("aaaaaaaa-2222-2222-2222-000000000001")

        # Restricted policy: only payments is allowed.
        policy = _RolePolicy(
            user_id=user_uuid,
            role_id=role_uuid,
            connection_id=conn_id,
            allowed_tables=[
                {"table": "payments", "columns": ["id", "order_id"]},
            ],
        )

        async def _provider(uid, cid):
            return policy

        accepted = _make_accepted_query(
            accepted_query_id=aq_id,
            user_id=user_uuid,
            generated_sql="SELECT orders.id FROM orders",
        )
        service, deps = _make_rerun_service(
            accepted_query=accepted,
            policy_provider=_provider,
        )

        result = await service.rerun_accepted_query(
            accepted_query_id=str(aq_id),
            user_id=str(user_uuid),
            connection_id=str(conn_id),
        )

        # Block returns EvaluatorRejection (NOT QueryResult, NOT None).
        assert isinstance(result, EvaluatorRejection), (
            f"expected EvaluatorRejection, got {type(result).__name__}: {result!r}"
        )
        assert result.message_key == "error.queryBlockedPolicy", (
            f"expected error.queryBlockedPolicy, got {result.message_key}"
        )
        for v in result.violations:
            assert v.rule == "role_authorization"
            assert v.message_key == "error.queryBlockedPolicy"
        # Executor NOT called.
        assert deps["executor"].calls == [], (
            f"executor should not be called when rerun is blocked; got {deps['executor'].calls!r}"
        )
        # Sanitization: forbidden tokens must not appear in the
        # rejection payload's serialized form.
        payload = result.model_dump()
        for token in _RERUN_FORBIDDEN_IN_RESPONSE:
            assert token not in str(payload), (
                f"forbidden token {token!r} leaked into rerun rejection payload: {payload!r}"
            )

    @pytest.mark.asyncio
    async def test_rerun_blocked_when_column_removed_from_policy(self):
        """Policy allows ``orders(id, customer_id)`` but the stored
        SQL selects ``orders.ssn``. The rerun must be blocked with
        ``error.queryBlockedPolicy``. No raw SQL, column, UUID, or
        user value leaks."""
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        user_uuid = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        role_uuid = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")
        aq_id = uuid.UUID("aaaaaaaa-3333-3333-3333-000000000001")

        # Restricted policy: orders(id, customer_id) — ssn removed.
        policy = _RolePolicy(
            user_id=user_uuid,
            role_id=role_uuid,
            connection_id=conn_id,
            allowed_tables=[
                {"table": "orders", "columns": ["id", "customer_id"]},
            ],
        )

        async def _provider(uid, cid):
            return policy

        accepted = _make_accepted_query(
            accepted_query_id=aq_id,
            user_id=user_uuid,
            generated_sql="SELECT orders.ssn FROM orders",
        )
        service, deps = _make_rerun_service(
            accepted_query=accepted,
            policy_provider=_provider,
        )

        result = await service.rerun_accepted_query(
            accepted_query_id=str(aq_id),
            user_id=str(user_uuid),
            connection_id=str(conn_id),
        )

        assert isinstance(result, EvaluatorRejection)
        assert result.message_key == "error.queryBlockedPolicy"
        assert deps["executor"].calls == []
        # Sanitization: the rejected column name and any other
        # internal token must not appear in the payload.
        payload = result.model_dump()
        for token in _RERUN_FORBIDDEN_IN_RESPONSE:
            assert token not in str(payload), (
                f"forbidden token {token!r} leaked into rerun rejection payload: {payload!r}"
            )
        # The stored SQL itself must never appear in the payload.
        assert "SELECT orders.ssn FROM orders" not in str(payload)
        assert "orders.ssn" not in str(payload)


# ─── 3. Missing policy row for role-bearing user fails closed ──────


class TestRerunFailClosedOnMissingPolicyRow:
    """Per PR #129: a user with a ``role_id`` but no matching
    ``role_connection_policies`` row for the connection must fail
    closed with a sanitized ``error.queryBlockedPolicy`` rejection.
    The LLM is never called (no LLM in rerun path), the executor is
    never called, and no internal details leak."""

    @pytest.mark.asyncio
    async def test_rerun_blocked_fail_closed_when_no_policy_row(self):
        """Wire the real production ``make_role_policy_provider`` and
        configure the DB so the user has a ``role_id`` but no
        ``role_connection_policies`` row exists. The rerun must
        block before executor with ``error.queryBlockedPolicy``."""
        from app.services.role_policy_provider import make_role_policy_provider

        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        user_uuid = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        role_uuid = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")
        aq_id = uuid.UUID("aaaaaaaa-4444-4444-4444-000000000001")

        accepted = _make_accepted_query(
            accepted_query_id=aq_id,
            user_id=user_uuid,
            generated_sql="SELECT orders.id FROM orders",
        )

        # Build the service with a real provider. Wire the DB so
        # the user lookup returns a user with role_id, and the
        # role_connection_policies lookup returns None.
        def _execute_side_effect(stmt, *args, **kwargs):
            stmt_str = str(stmt)
            if "FROM users" in stmt_str:
                user = MagicMock()
                user.id = user_uuid
                user.role_id = role_uuid
                user.role = "viewer"
                return MagicMock(scalar_one_or_none=MagicMock(return_value=user))
            if "role_connection_policies" in stmt_str:
                return MagicMock(scalar_one_or_none=MagicMock(return_value=None))
            if "user_identities" in stmt_str:
                return MagicMock(scalar_one_or_none=MagicMock(return_value=None))
            return MagicMock()

        db = MagicMock()
        db.execute = MagicMock(side_effect=_execute_side_effect)
        db.flush = AsyncMock()

        service, deps = _make_rerun_service(
            accepted_query=accepted,
            policy_provider=make_role_policy_provider(db),
        )
        # Replace the stubbed db with the wired one.
        service._db_session = db

        result = await service.rerun_accepted_query(
            accepted_query_id=str(aq_id),
            user_id=str(user_uuid),
            connection_id=str(conn_id),
        )

        assert isinstance(result, EvaluatorRejection), (
            f"expected fail-closed EvaluatorRejection, got {type(result).__name__}: {result!r}"
        )
        assert result.message_key == "error.queryBlockedPolicy"
        assert deps["executor"].calls == []
        # No internal details leak.
        payload = result.model_dump()
        for token in _RERUN_FORBIDDEN_IN_RESPONSE:
            assert token not in str(payload), (
                f"forbidden token {token!r} leaked into fail-closed rerun rejection payload: {payload!r}"
            )
        # LLM never called.
        if hasattr(service._llm, "generate_sql"):
            service._llm.generate_sql.assert_not_called()


# ─── 4. Cross-user or non-existent accepted query → None ────────────


class TestRerunNotFound:
    """``AcceptedQueryRepository.get_by_id(query_id, user_id)`` is
    scoped by ``user_id`` at the SQL ``WHERE`` clause. A cross-user
    or non-existent ``accepted_query_id`` returns ``None`` from the
    repo and the rerun path surfaces ``None`` so the caller can
    raise a sanitized 404. No execution, no LLM, no policy lookup
    even attempted (the cross-user is blocked at the repo)."""

    @pytest.mark.asyncio
    async def test_rerun_returns_none_when_accepted_query_not_found(self):
        """Cross-user attempt: user A's accepted query is not
        visible to user B. The repo's ``get_by_id`` (which has
        ``WHERE accepted_queries.user_id = :user_id``) returns
        ``None``; the rerun path returns ``None``."""
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        user_b = uuid.UUID("550e8400-e29b-41d4-a716-446655440002")
        role_b = uuid.UUID("660e8400-e29b-41d4-a716-446655440002")
        aq_id = uuid.UUID("aaaaaaaa-5555-5555-5555-000000000001")

        async def _provider(uid, cid):
            return _RolePolicy(
                user_id=user_b,
                role_id=role_b,
                connection_id=cid,
                allowed_tables=[
                    {"table": "orders", "columns": ["id", "customer_id", "ssn"]},
                    {"table": "payments", "columns": ["id", "order_id"]},
                ],
            )

        # accepted_query=None mimics the cross-user repo result.
        service, deps = _make_rerun_service(
            accepted_query=None,
            policy_provider=_provider,
        )

        result = await service.rerun_accepted_query(
            accepted_query_id=str(aq_id),
            user_id=str(user_b),
            connection_id=str(conn_id),
        )

        assert result is None, (
            f"expected None for cross-user / non-existent accepted query, got {type(result).__name__}: {result!r}"
        )
        # The repo's get_by_id was called exactly once with the
        # user's id (so the WHERE clause scoped the lookup).
        assert deps["repo"].get_by_id.await_count == 1
        call_args = deps["repo"].get_by_id.await_args
        assert call_args is not None
        # The second positional arg is user_id; assert it equals user_b.
        assert call_args.args[1] == user_b, f"expected get_by_id called with user_id={user_b}, got {call_args.args[1]}"
        # Executor NOT called.
        assert deps["executor"].calls == []


# ─── 5. Column masking preserved on rerun ───────────────────────────


class TestRerunColumnMaskingPreserved:
    """Per FR-132. A column in the role's ``column_masks`` list
    that the user is otherwise allowed to SELECT remains allowed;
    the masking service is still applied to the executor's result.
    Rerun must not short-circuit masking when auth passes."""

    @pytest.mark.asyncio
    async def test_masked_column_in_stored_sql_remains_allowed(self):
        """Stored SQL ``SELECT orders.ssn FROM orders`` is allowed
        (role's ``allowed_columns`` includes ``ssn`` for ``orders``),
        and ``ssn`` is in the role's ``column_masks``. The rerun
        must reach the executor once, and the policy enforcement
        service's ``apply_column_masks`` must be invoked with the
        executor's result. No LLM call."""
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        user_uuid = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        role_uuid = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")
        aq_id = uuid.UUID("aaaaaaaa-6666-6666-6666-000000000001")

        # Allowed + masked. allowed_columns includes ssn, and
        # column_masks says ssn is masked (so the auth check
        # passes, and the masking service replaces ssn with
        # "***" in the result).
        policy = _RolePolicy(
            user_id=user_uuid,
            role_id=role_uuid,
            connection_id=conn_id,
            allowed_tables=[
                {"table": "orders", "columns": ["id", "customer_id", "ssn"]},
            ],
            column_masks=[{"table": "orders", "column": "ssn"}],
        )

        async def _provider(uid, cid):
            return policy

        accepted = _make_accepted_query(
            accepted_query_id=aq_id,
            user_id=user_uuid,
            generated_sql="SELECT orders.ssn FROM orders",
        )

        # Capture calls to apply_column_masks; return a sentinel
        # result so we can assert masking was applied.
        masking_calls: list[dict] = []

        from app.schemas.query import ColumnMeta, QueryResult

        def _apply_masks(result, masks):
            masking_calls.append({"result": result, "masks": masks})
            # Return a real QueryResult with the masked values so
            # the rerun path returns a model-valid response.
            return QueryResult(
                kind="result",
                attempt_id=result.attempt_id,
                session_id=result.session_id,
                question=result.question,
                generated_sql=result.generated_sql,
                columns=[
                    ColumnMeta(name="ssn", type="text", masked=True),
                ],
                rows=[["***"]],
                row_count=1,
                attempt_number=1,
                is_last_auto_retry=False,
                accepted_query_id=result.accepted_query_id,
            )

        # Row filter stub: no row filters, so apply_row_filters is
        # not expected to be called.
        def _apply_filters(sql, row_filters, **kwargs):
            raise AssertionError("apply_row_filters should not be called when no row_filters are configured")

        service, deps = _make_rerun_service(
            accepted_query=accepted,
            policy_provider=_provider,
            apply_row_filters=_apply_filters,
            apply_column_masks=_apply_masks,
        )

        result = await service.rerun_accepted_query(
            accepted_query_id=str(aq_id),
            user_id=str(user_uuid),
            connection_id=str(conn_id),
        )

        # Allowed → QueryResult. Executor called once.
        assert isinstance(result, QueryResult)
        assert len(deps["executor"].calls) == 1
        assert deps["executor"].calls[0]["sql"] == "SELECT orders.ssn FROM orders"
        # Masking was applied.
        assert len(masking_calls) == 1, (
            f"expected apply_column_masks called once, got {len(masking_calls)}: {masking_calls!r}"
        )
        assert masking_calls[0]["masks"] == [{"table": "orders", "column": "ssn"}]
        # The returned QueryResult is the masked one.
        assert result.rows == [["***"]]
        # No LLM call.
        if hasattr(service._llm, "generate_sql"):
            service._llm.generate_sql.assert_not_called()


# ─── 6. Row filter applied before execution on rerun ────────────────


class TestRerunRowFilterApplied:
    """Per FR-131. When the user's current role has ``row_filters``
    for the connection, the stored SQL is rewritten via
    ``PolicyEnforcementService.apply_row_filters`` before the
    executor is called, and the bound parameters are passed
    through to the executor. Defence in depth: user values are
    never interpolated into the SQL string."""

    @pytest.mark.asyncio
    async def test_rerun_rewrites_sql_and_binds_params(self):
        """Stored SQL ``SELECT orders.id FROM orders``; policy
        adds a row filter ``customer_id = {user.subject_id}``.
        The rerun calls ``apply_row_filters`` with the stored SQL,
        receives a ``BoundSql`` whose ``.sql`` is the rewritten
        query, and forwards ``.params`` to the executor. The
        original SQL string is NOT what reaches the executor."""
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        user_uuid = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        role_uuid = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")
        aq_id = uuid.UUID("aaaaaaaa-7777-7777-7777-000000000001")

        policy = _RolePolicy(
            user_id=user_uuid,
            role_id=role_uuid,
            connection_id=conn_id,
            allowed_tables=[
                {"table": "orders", "columns": ["id", "customer_id", "ssn"]},
            ],
            row_filters=[
                {
                    "table": "orders",
                    "filter": "customer_id = {user.subject_id}",
                }
            ],
            user_context={
                "email": "alice@example.com",
                "subject_id": "subject-abc-123",
                "role": "viewer",
            },
        )

        async def _provider(uid, cid):
            return policy

        accepted = _make_accepted_query(
            accepted_query_id=aq_id,
            user_id=user_uuid,
            generated_sql="SELECT orders.id FROM orders",
        )

        # Stub apply_row_filters: return BoundSql with the
        # rewritten SQL and the bound params.
        filter_calls: list[dict] = []

        class _BoundSql:
            def __init__(self, sql, params):
                self.sql = sql
                self.params = params

        def _apply_filters(sql, row_filters, **kwargs):
            filter_calls.append(
                {
                    "sql": sql,
                    "row_filters": row_filters,
                    "user_context": kwargs.get("user_context"),
                    "dialect": kwargs.get("dialect"),
                }
            )
            return _BoundSql(
                sql="SELECT orders.id FROM orders WHERE customer_id = $1",
                params=("subject-abc-123",),
            )

        # No column masks for this test.
        def _apply_masks(result, masks):
            raise AssertionError("apply_column_masks should not be called when no column_masks are configured")

        service, deps = _make_rerun_service(
            accepted_query=accepted,
            policy_provider=_provider,
            apply_row_filters=_apply_filters,
            apply_column_masks=_apply_masks,
        )

        result = await service.rerun_accepted_query(
            accepted_query_id=str(aq_id),
            user_id=str(user_uuid),
            connection_id=str(conn_id),
        )

        # Allowed → QueryResult.
        assert isinstance(result, QueryResult)
        # apply_row_filters called with the stored SQL.
        assert len(filter_calls) == 1
        assert filter_calls[0]["sql"] == "SELECT orders.id FROM orders"
        assert filter_calls[0]["row_filters"] == [
            {
                "table": "orders",
                "filter": "customer_id = {user.subject_id}",
            }
        ]
        # User values passed via user_context, not via SQL string.
        assert filter_calls[0]["user_context"]["subject_id"] == "subject-abc-123"
        # Executor called once with the REWRITTEN SQL + bound params.
        assert len(deps["executor"].calls) == 1
        assert deps["executor"].calls[0]["sql"] == "SELECT orders.id FROM orders WHERE customer_id = $1"
        assert deps["executor"].calls[0]["params"] == ("subject-abc-123",)
        # No LLM call.
        if hasattr(service._llm, "generate_sql"):
            service._llm.generate_sql.assert_not_called()
        # Accepted row not mutated.
        deps["repo"].create.assert_not_called()
        deps["repo"].update_feedback.assert_not_called()


# ─── 7. Legacy role_id=None path: rerun executes unchanged ────────


class TestRerunLegacyNoPolicyPath:
    """When the role policy provider returns ``None`` (user has no
    ``role_id``, Phase 1-3 legacy admin), the rerun path must
    execute the stored SQL with no policy enforcement. Row filters
    and column masks are no-ops; the auth rule is not run; the
    LLM is not called. The behaviour matches the
    ``policy is None`` branch in ``submit_question``."""

    @pytest.mark.asyncio
    async def test_rerun_executes_when_provider_returns_none(self):
        """Provider returns None for a role-less user. The rerun
        path must execute the stored SQL once and return a
        ``QueryResult``. No policy enforcement calls are made."""
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        user_uuid = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        aq_id = uuid.UUID("aaaaaaaa-8888-8888-8888-000000000001")

        async def _provider(uid, cid):
            return None  # role_id=None / legacy path.

        accepted = _make_accepted_query(
            accepted_query_id=aq_id,
            user_id=user_uuid,
            generated_sql="SELECT orders.id FROM orders",
        )

        filter_calls: list[dict] = []
        mask_calls: list[dict] = []

        def _apply_filters(sql, row_filters, **kwargs):
            filter_calls.append(sql)
            from app.services.policy_enforcement import BoundSql

            return BoundSql(sql=sql, params=())

        def _apply_masks(result, masks):
            mask_calls.append(masks)
            return result

        service, deps = _make_rerun_service(
            accepted_query=accepted,
            policy_provider=_provider,
            apply_row_filters=_apply_filters,
            apply_column_masks=_apply_masks,
        )

        result = await service.rerun_accepted_query(
            accepted_query_id=str(aq_id),
            user_id=str(user_uuid),
            connection_id=str(conn_id),
        )

        assert isinstance(result, QueryResult)
        # Executor called once with the stored SQL.
        assert len(deps["executor"].calls) == 1
        assert deps["executor"].calls[0]["sql"] == "SELECT orders.id FROM orders"
        # No row-filter or column-mask work when policy is None.
        assert filter_calls == []
        assert mask_calls == []
        # LLM not called.
        if hasattr(service._llm, "generate_sql"):
            service._llm.generate_sql.assert_not_called()
        # Accepted row not mutated.
        deps["repo"].create.assert_not_called()
        deps["repo"].update_feedback.assert_not_called()
