"""T-719 — Query lifecycle audit logging tests (RED).

Per FR-140 / SC-059 / SC-061. Every query lifecycle
event emits an audit entry through ``AuditService.log``:

- submit          -> query.submit
- validation pass -> query.validate.pass
- validation fail -> query.validate.fail
- execute         -> query.execute (success or failure outcome)
- accept          -> query.accept
- reject          -> query.reject
- policy block    -> access.denied
                     (deny-all fail-closed BEFORE LLM,
                      role_authorization AFTER LLM)

Sanitization invariants (defence in depth):

- The audit ``context`` dict must never contain:
  - the raw generated/stored SQL string
  - the user-supplied question text (only length)
  - table or column names that caused a role-authorization
    block (only the constant reason)
  - DB host / port / username / credential / token
  - SAML / XML / cert / assertion fragments
  - stack traces or raw driver errors
  - row / column data from the executed result
- Resource IDs (accepted_query_id, attempt_id) are
  present in the audit ``resource_id`` field (standard
  per existing audit model) but never in ``context``.
- Audit context for execution failure only includes
  the failure ``reason`` (timeout / error) and the
  ``attempt_id``; never the raw driver error message.

Audit failure path: the existing project pattern
(role_service, sso_service) does NOT wrap
``AuditService.log`` in try/except. Audit failures
propagate. This is the project-wide fail-closed
contract. The query service follows the same
pattern: audit exceptions propagate, no swallowing.

These tests patch
``app.services.audit_service.AuditService.log`` (the
canonical module path; ``query_service`` imports
the class via ``from app.services.audit_service
import AuditService``) and inspect call_args to
verify action / outcome / context / actor_identity.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.attempt_store import EphemeralAttempt, store_attempt
from app.services.query_service import QueryService

# ── helpers ─────────────────────────────────────────────────────────────


# Forbidden tokens for audit ``context`` redaction tests.
# Mirrors the rerun test pattern but scoped to the audit
# context dict only (not the API response). Resource IDs
# (accepted_query_id, attempt_id) are NOT forbidden in
# resource_id per the existing audit model.
_AUDIT_FORBIDDEN_IN_CONTEXT = (
    # raw SQL fragment
    "SELECT orders.ssn FROM orders WHERE ssn = '123-45-6789'",
    "SELECT ssn FROM payments",
    # question text leakage
    "How many customer SSNs?",
    "Show me the database password",
    # table / column from a role-auth block
    "orders.ssn",
    "payments.ssn",
    # DB driver / host / port / driver internals
    "asyncpg",
    "asyncio",
    "10.0.0.42",
    "5432",
    "svc-prod-db",
    # credentials / tokens
    "admin_pw",
    "secret-token",
    "sk-12345",
    # SAML / cert / XML / assertion
    "saml-xml",
    "-----BEGIN CERT-----",
    "PHNhbWw+",
    # stack traces / driver errors
    "Traceback",
    'File "',
    "psycopg2",
    "pymysql",
    "pyodbc",
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


class _RecordingLLM:
    def __init__(self, sql: str = "SELECT orders.id FROM orders"):
        self._sql = sql
        self.calls: list[dict] = []

    async def generate_sql(
        self,
        question,
        schema_context,
        negative_examples=None,
        conversation_history=None,
        target_dialect=None,
    ):
        self.calls.append(
            {
                "question": question,
                "schema_context": schema_context,
                "negative_examples": negative_examples,
                "conversation_history": conversation_history,
                "target_dialect": target_dialect,
            }
        )
        return self._sql


class _FailingEvaluator:
    """Returns a failed evaluation with the given rule name."""

    def __init__(self, rule: str = "schema_validation", message_key: str = "error.evaluatorRejected"):
        self._rule = rule
        self._message_key = message_key
        self.calls: list[dict] = []

    async def evaluate(self, sql, schema):
        from dataclasses import dataclass

        @dataclass
        class _Violation:
            rule_name: str
            message_key: str

        @dataclass
        class _Result:
            passed: bool
            violations: list

        self.calls.append({"sql": sql, "schema": schema})
        return _Result(
            passed=False,
            violations=[_Violation(rule_name=self._rule, message_key=self._message_key)],
        )


class _PassThroughEvaluator:
    """Delegates to an empty-pipeline Evaluator (no rules)."""

    def __init__(self):
        from app.evaluator.pipeline import Evaluator

        self._inner = Evaluator(rules=[])
        self.calls: list[dict] = []

    async def evaluate(self, sql, schema):
        self.calls.append({"sql": sql, "schema": schema})
        return await self._inner.evaluate(sql, schema)


class _RecordingAdapter:
    def __init__(self, columns=None, rows=None):
        self._columns = columns or [{"name": "id", "type": "integer"}]
        self._rows = rows or [[1]]
        self.calls: list[dict] = []

    async def execute(self, sql, params=(), **_kwargs):
        self.calls.append({"sql": sql, "params": params})

        class _Result:
            def __init__(self, columns, rows):
                self.columns = columns
                self.rows = rows

        return _Result(self._columns, self._rows)


class _TimingOutAdapter:
    """Simulates source DB timeout for the execution failure test."""

    async def execute(self, sql, params=(), **_kwargs):
        import asyncio

        await asyncio.sleep(0)
        raise TimeoutError("connection to 10.0.0.42:5432 timed out after 30s")


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

    async def eval(self, script, num_keys, *args):
        return 1


def _make_user_mock(
    user_id="550e8400-e29b-41d4-a716-446655440000",
    role_id="660e8400-e29b-41d4-a716-446655440000",
    username="alice@example.com",
):
    user = MagicMock()
    user.id = uuid.UUID(user_id)
    user.role_id = uuid.UUID(role_id)
    user.username = username
    user.display_name = "Alice"
    user.is_builtin = False
    user.auth_provider = "oidc"
    return user


def _make_service(
    *,
    user: MagicMock | None = None,
    role_policy_provider=None,
    llm=None,
    evaluator=None,
    adapter=None,
    connection_id="770e8400-e29b-41d4-a716-446655440000",
    policies_by_connection: dict[uuid.UUID, _RolePolicy] | None = None,
):
    """Build a QueryService with recording deps for audit tests.

    Mirrors ``_make_service`` in test_query_flow_policy.py
    with a real-username user mock (audit needs string
    actor_identity).
    """
    if policies_by_connection is not None:

        async def _provider(uid, cid):
            return policies_by_connection.get(cid)

        role_policy_provider = role_policy_provider or _provider

    db = AsyncMock()
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    user_mock = user or _make_user_mock(user_id=user_id)

    def _execute_side_effect(stmt, *args, **kwargs):
        async def _coro():
            stmt_str = str(stmt)
            if "FROM users" in stmt_str:
                return MagicMock(scalar_one_or_none=MagicMock(return_value=user_mock))
            # app_config / default lookup
            return MagicMock(fetchone=MagicMock(return_value=(3,)))

        return _coro()

    db.execute = _execute_side_effect
    db.flush = AsyncMock()

    repo = MagicMock()
    repo.list_by_session = AsyncMock(return_value=[])
    repo.get_latest_by_session = AsyncMock(return_value=None)
    repo.get_by_attempt_id = AsyncMock(return_value=None)
    # _saved is the returned accepted-query ORM row. Use a real
    # string id (audit resource_id) + real string scalar fields
    # (AcceptedQuerySummary is a pydantic model that rejects
    # MagicMock on string fields). accepted_at is a real
    # datetime (the service calls .isoformat() on it).
    from datetime import UTC, datetime

    _saved = MagicMock(
        id="aaaaaaaa-0000-0000-0000-000000000001",
        question_text="How many?",
        generated_sql="SELECT 1",
        accepted_at=datetime(2026, 6, 5, tzinfo=UTC),
        database_connection_id=uuid.UUID("770e8400-e29b-41d4-a716-446655440000"),
    )
    repo.create = AsyncMock(return_value=_saved)

    session_repo = MagicMock()
    session_repo.create = AsyncMock(return_value=MagicMock(id="550e8400-e29b-41d4-a716-446655440001"))
    session_repo.get_by_id = AsyncMock(return_value=None)
    session_repo.update_last_activity = AsyncMock(return_value=True)
    session_repo.update_preview_text = AsyncMock(return_value=True)

    actual_llm = llm or _RecordingLLM()
    actual_evaluator = evaluator or _PassThroughEvaluator()

    return QueryService(
        accepted_query_repository=repo,
        session_repository=session_repo,
        db_session=db,
        redis=_FakeRedis(),
        llm=actual_llm,
        evaluator=actual_evaluator,
        source_db_executor=MagicMock(),  # not used when adapter set
        source_db_adapter=adapter,
        schema_context=_schema_context(),
        llm_provider="stub",
        connection_id=connection_id,
        role_policy_provider=role_policy_provider,
    ), {
        "repo": repo,
        "session_repo": session_repo,
        "db": db,
        "llm": actual_llm,
        "evaluator": actual_evaluator,
        "user_id": user_id,
    }


def _audit_actions(mock_audit) -> list:
    """Return list of AuditActionType enums from mock_audit calls."""
    out: list = []
    for call in mock_audit.call_args_list:
        action = call.kwargs.get("action") if call.kwargs else None
        if action is None and call.args:
            action = call.args[0]
        if action is not None:
            out.append(action)
    return out


def _audit_context(mock_audit, action):
    """Return the context dict from the first call matching ``action``."""
    for call in mock_audit.call_args_list:
        a = call.kwargs.get("action") if call.kwargs else None
        if a is None and call.args:
            a = call.args[0]
        if a == action:
            return call.kwargs.get("context") or {}
    return {}


# ── 1. Submit success ──────────────────────────────────────────────────


@pytest.mark.asyncio
class TestSubmitSuccessAuditLogging:
    """FR-140: submit success emits query.submit, query.validate.pass,
    query.execute in that order."""

    async def test_submit_success_logs_submit_validate_pass_execute_in_order(self):
        from app.db.models.enums import AuditActionType

        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
        )
        service, _ = _make_service(
            adapter=_RecordingAdapter(),
            policies_by_connection={conn_id: policy},
        )

        with patch(
            "app.services.audit_service.AuditService.log",
            new_callable=AsyncMock,
        ) as mock_audit:
            result = await service.submit_question(
                http_session_id="http-sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                question="How many orders?",
            )

        assert isinstance(result, object)
        actions = _audit_actions(mock_audit)
        assert actions == [
            AuditActionType.QUERY_SUBMIT,
            AuditActionType.QUERY_VALIDATE_PASS,
            AuditActionType.QUERY_EXECUTE,
        ], f"Audit calls in unexpected order: {actions}"


# ── 2. Evaluator validation failure ────────────────────────────────────


@pytest.mark.asyncio
class TestEvaluatorFailAuditLogging:
    """FR-140: evaluator failure emits query.validate.fail and
    does NOT emit query.execute (the SQL never reached the executor)."""

    async def test_evaluator_validation_failure_logs_validate_fail_and_skips_execute(self):
        from app.db.models.enums import AuditActionType

        service, deps = _make_service(
            evaluator=_FailingEvaluator(rule="schema_validation"),
            adapter=_RecordingAdapter(),
        )

        with patch(
            "app.services.audit_service.AuditService.log",
            new_callable=AsyncMock,
        ) as mock_audit:
            result = await service.submit_question(
                http_session_id="http-sess-1",
                user_id=deps["user_id"],
                question="Bad question",
            )

        from app.schemas.query import EvaluatorRejection

        assert isinstance(result, EvaluatorRejection)
        actions = _audit_actions(mock_audit)
        assert AuditActionType.QUERY_SUBMIT in actions
        assert AuditActionType.QUERY_VALIDATE_FAIL in actions
        assert AuditActionType.QUERY_EXECUTE not in actions, (
            f"QUERY_EXECUTE must NOT be logged when the evaluator fails: {actions}"
        )


# ── 3. Policy block before LLM (deny-all fail-closed) ──────────────────


@pytest.mark.asyncio
class TestPolicyBlockBeforeLlmAuditLogging:
    """FR-140: deny-all fail-closed (user has role_id but
    no role_connection_policies row) emits access.denied
    BEFORE the LLM is called. No raw SQL / schema / user
    values in the audit context."""

    async def test_deny_all_policy_block_logs_access_denied_no_sql(self):
        from app.db.models.enums import AuditActionType

        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        # Deny-all: empty allowed_tables.
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[],
        )
        service, deps = _make_service(
            llm=_RecordingLLM(),
            adapter=_RecordingAdapter(),
            policies_by_connection={conn_id: policy},
        )

        with patch(
            "app.services.audit_service.AuditService.log",
            new_callable=AsyncMock,
        ) as mock_audit:
            result = await service.submit_question(
                http_session_id="http-sess-1",
                user_id=deps["user_id"],
                question="How many customer SSNs?",
            )

        from app.schemas.query import EvaluatorRejection

        assert isinstance(result, EvaluatorRejection)
        # LLM must NOT be called on the deny-all path.
        assert len(deps["llm"].calls) == 0, "LLM must not be called when policy is deny-all"
        actions = _audit_actions(mock_audit)
        assert AuditActionType.QUERY_SUBMIT in actions
        assert AuditActionType.ACCESS_DENIED in actions

        # Audit context for the access.denied event must NOT
        # contain raw question text, SQL, or sensitive tokens.
        ctx = _audit_context(mock_audit, AuditActionType.ACCESS_DENIED)
        ctx_str = str(ctx)
        for token in _AUDIT_FORBIDDEN_IN_CONTEXT:
            assert token not in ctx_str, f"Forbidden token {token!r} found in access.denied audit context: {ctx}"


# ── 4. Policy block after LLM (role-authorization) ─────────────────────


@pytest.mark.asyncio
class TestPolicyBlockAfterLlmAuditLogging:
    """FR-140: role-authorization block (LLM generated SQL
    referencing a table outside the role's policy) emits
    access.denied AFTER query.validate.pass. No raw SQL,
    table name, or column name leaks in the audit context."""

    async def test_role_authorization_block_logs_access_denied_no_table_or_column(self):
        from app.db.models.enums import AuditActionType

        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        # Policy only allows ``public_reports``; the LLM is
        # pinned to return ``SELECT ssn FROM payments`` so
        # role-authorization must block on ``payments.ssn``.
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "public_reports", "columns": ["id"]}],
        )
        service, deps = _make_service(
            llm=_RecordingLLM(sql="SELECT ssn FROM payments"),
            evaluator=_PassThroughEvaluator(),
            adapter=_RecordingAdapter(),
            policies_by_connection={conn_id: policy},
        )

        with patch(
            "app.services.audit_service.AuditService.log",
            new_callable=AsyncMock,
        ) as mock_audit:
            result = await service.submit_question(
                http_session_id="http-sess-1",
                user_id=deps["user_id"],
                question="Show me customer SSNs",
            )

        from app.schemas.query import EvaluatorRejection

        assert isinstance(result, EvaluatorRejection)
        actions = _audit_actions(mock_audit)
        assert AuditActionType.QUERY_SUBMIT in actions
        assert AuditActionType.QUERY_VALIDATE_PASS in actions
        assert AuditActionType.ACCESS_DENIED in actions

        # No execute on the role-auth block path.
        assert AuditActionType.QUERY_EXECUTE not in actions

        # Audit context must NOT contain the raw SQL, the
        # offending table, or the offending column.
        ctx = _audit_context(mock_audit, AuditActionType.ACCESS_DENIED)
        ctx_str = str(ctx)
        for forbidden in (
            "SELECT ssn FROM payments",
            "payments",
            "ssn",
        ):
            assert forbidden not in ctx_str, f"Forbidden token {forbidden!r} found in role-auth audit context: {ctx}"


# ── 5. Accept ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestAcceptAuditLogging:
    """FR-140: user accepting a query result emits query.accept."""

    async def test_accept_query_logs_accept_event(self):
        from app.db.models.enums import AuditActionType

        service, deps = _make_service()
        http_session_id = "http-sess-1"
        attempt_id = str(uuid.uuid4())

        # Set up the ephemeral attempt + active_attempt mapping
        # the accept_query flow expects.
        await service._redis.set(f"active_attempt:{http_session_id}", attempt_id)
        ephemeral = EphemeralAttempt(
            attempt_id=attempt_id,
            session_id=http_session_id,
            user_id=deps["user_id"],
            state="EXECUTED",
            sql="SELECT 1",
            question="How many?",
        )
        await store_attempt(ephemeral, http_session_id, service._redis)

        with patch(
            "app.services.audit_service.AuditService.log",
            new_callable=AsyncMock,
        ) as mock_audit:
            summary = await service.accept_query(
                http_session_id=http_session_id,
                user_id=deps["user_id"],
                attempt_id=attempt_id,
            )

        actions = _audit_actions(mock_audit)
        assert AuditActionType.QUERY_ACCEPT in actions, f"Expected QUERY_ACCEPT in audit calls, got {actions}"
        # resource_id should be the accepted query id (audit
        # standard; not a leak).
        accept_calls = [
            c
            for c in mock_audit.call_args_list
            if (c.kwargs.get("action") if c.kwargs else None) == AuditActionType.QUERY_ACCEPT
            or (c.args[0] if c.args else None) == AuditActionType.QUERY_ACCEPT
        ]
        assert len(accept_calls) == 1
        call = accept_calls[0]
        assert call.kwargs.get("resource_type") == "accepted_query"
        assert call.kwargs.get("resource_id") == str(summary.id)


# ── 6. Reject ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestRejectAuditLogging:
    """FR-140: user rejecting a query result emits query.reject."""

    async def test_reject_query_logs_reject_event(self):
        from app.db.models.enums import AuditActionType

        service, deps = _make_service()
        http_session_id = "http-sess-1"
        attempt_id = str(uuid.uuid4())

        # reject_query (via regenerate_query) needs an active
        # attempt + ephemeral attempt in Redis.
        await service._redis.set(f"active_attempt:{http_session_id}", attempt_id)
        ephemeral = EphemeralAttempt(
            attempt_id=attempt_id,
            session_id=http_session_id,
            user_id=deps["user_id"],
            state="EXECUTED",
            sql="SELECT 1",
            question="How many?",
        )
        await store_attempt(ephemeral, http_session_id, service._redis)

        with patch(
            "app.services.audit_service.AuditService.log",
            new_callable=AsyncMock,
        ) as mock_audit:
            # Patch LLM/evaluator on the regenerate path so
            # the call returns a RefinePrompt quickly. The
            # point of this test is the QUERY_REJECT event.
            with patch.object(
                service._llm,
                "generate_sql",
                new=AsyncMock(return_value="SELECT 1"),
            ):
                await service.reject_query(
                    attempt_id=attempt_id,
                    http_session_id=http_session_id,
                )

        actions = _audit_actions(mock_audit)
        assert AuditActionType.QUERY_REJECT in actions, f"Expected QUERY_REJECT in audit calls, got {actions}"


# ── 7. Source DB timeout / execution failure ───────────────────────────


@pytest.mark.asyncio
class TestSourceDbTimeoutAuditLogging:
    """FR-140: source DB execution failure (timeout) logs
    query.execute with outcome='failure'. The audit context
    contains only the failure reason + attempt_id; no raw
    driver error, host, port, or credential."""

    async def test_source_db_timeout_logs_execution_failure_sanitized(self):
        from app.db.models.enums import AuditActionType

        service, deps = _make_service(
            adapter=_TimingOutAdapter(),
        )

        with patch(
            "app.services.audit_service.AuditService.log",
            new_callable=AsyncMock,
        ) as mock_audit:
            with pytest.raises(HTTPException) as exc_info:
                await service.submit_question(
                    http_session_id="http-sess-1",
                    user_id=deps["user_id"],
                    question="How many orders?",
                )

        assert exc_info.value.status_code == 504

        actions = _audit_actions(mock_audit)
        assert AuditActionType.QUERY_SUBMIT in actions
        assert AuditActionType.QUERY_VALIDATE_PASS in actions

        # Find the QUERY_EXECUTE call(s) and assert one
        # is a failure outcome.
        execute_calls = [
            c
            for c in mock_audit.call_args_list
            if (c.kwargs.get("action") if c.kwargs else None) == AuditActionType.QUERY_EXECUTE
        ]
        assert len(execute_calls) >= 1
        failure_calls = [c for c in execute_calls if (c.kwargs.get("outcome") if c.kwargs else "success") != "success"]
        assert len(failure_calls) == 1, f"Expected exactly one QUERY_EXECUTE failure outcome, got: {execute_calls}"

        # Failure context: no raw driver error / host / port /
        # credential / SAML / cert.
        ctx = failure_calls[0].kwargs.get("context") or {}
        ctx_str = str(ctx)
        for token in _AUDIT_FORBIDDEN_IN_CONTEXT:
            assert token not in ctx_str, f"Forbidden token {token!r} found in execution-failure audit context: {ctx}"


# ── 8. Audit context redaction (cross-cutting) ─────────────────────────


@pytest.mark.asyncio
class TestAuditContextRedaction:
    """FR-143 / SC-061: every audit ``context`` dict on the
    query lifecycle path contains no raw SQL, no question
    text, no secrets, no host/port/credentials, no SAML /
    cert / assertion fragments, no stack traces."""

    async def test_audit_context_has_no_secrets_or_user_values(self):
        from app.db.models.enums import AuditActionType

        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            # Allow ssn so the role-auth rule passes and execution
            # actually runs; the redaction assertions below
            # verify the SQL fragment never reaches the audit
            # context regardless.
            allowed_tables=[{"table": "orders", "columns": ["id", "ssn"]}],
        )
        service, deps = _make_service(
            llm=_RecordingLLM(sql="SELECT orders.id FROM orders WHERE ssn = '123-45-6789'"),
            adapter=_RecordingAdapter(),
            policies_by_connection={conn_id: policy},
        )

        with patch(
            "app.services.audit_service.AuditService.log",
            new_callable=AsyncMock,
        ) as mock_audit:
            await service.submit_question(
                http_session_id="http-sess-1",
                user_id=deps["user_id"],
                question="Show me the database password admin_pw",
            )

        assert mock_audit.call_args_list, "No audit calls were made"
        for call in mock_audit.call_args_list:
            ctx = (call.kwargs.get("context") or {}) if call.kwargs else {}
            ctx_str = str(ctx)
            for token in _AUDIT_FORBIDDEN_IN_CONTEXT:
                assert token not in ctx_str, f"Forbidden token {token!r} found in audit context: {ctx}"

        # Sanity: at least the three expected events were emitted.
        actions = _audit_actions(mock_audit)
        assert AuditActionType.QUERY_SUBMIT in actions
        assert AuditActionType.QUERY_VALIDATE_PASS in actions
        assert AuditActionType.QUERY_EXECUTE in actions


# ── 9. Audit service failure path ──────────────────────────────────────


@pytest.mark.asyncio
class TestAuditServiceFailurePath:
    """The project pattern (role_service, sso_service) does
    NOT wrap ``AuditService.log`` in try/except. Audit
    failures propagate (fail-closed). The query service
    follows the same pattern: an audit exception is NOT
    swallowed and the same exception is raised out of the
    query service call. This preserves the project-wide
    contract that audit writes are part of the operation,
    not best-effort."""

    async def test_audit_service_failure_propagates_fail_closed(self):
        service, deps = _make_service(
            adapter=_RecordingAdapter(),
        )

        with patch(
            "app.services.audit_service.AuditService.log",
            new_callable=AsyncMock,
            side_effect=RuntimeError("audit DB write failed"),
        ) as _mock_audit:
            with pytest.raises(RuntimeError) as exc_info:
                await service.submit_question(
                    http_session_id="http-sess-1",
                    user_id=deps["user_id"],
                    question="How many?",
                )

        assert "audit DB write failed" in str(exc_info.value), (
            f"Audit exception did not propagate as-is: {exc_info.value!r}"
        )
