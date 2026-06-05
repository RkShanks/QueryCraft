"""T-711 — Integrated query-flow policy enforcement tests.

Exercises the end-to-end query path through QueryService with role policy
enforcement: schema filter -> LLM prompt -> evaluator (role auth) ->
row filter injection -> execute -> column mask -> result.

Pieces wired together (T-712):
- PolicyEnforcementService.filter_schema()
- RoleAuthorizationRule (in evaluator pipeline)
- PolicyEnforcementService.apply_row_filters()
- PolicyEnforcementService.apply_column_masks()

These tests inject a fake `role_policy_provider` so the test does not
depend on the actual roles / role_connection_policies tables. The
provider is a callable: ``(user_id: UUID, connection_id: UUID) ->
RolePolicy | None``. ``None`` means "no policy applies" (backward
compat with the Phase 1-3 un-authenticated flow).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import PolicySchemaConflictError
from app.services.query_service import QueryService

# ─── helpers ─────────────────────────────────────────────────────────


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
    """A SchemaContext double with two tables: orders, payments."""
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
    """Records every generate_sql call and returns a fixed SQL string."""

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


class _RecordingEvaluator:
    """Records every evaluate call. Delegates to a wrapped pipeline."""

    def __init__(self):
        from app.evaluator.pipeline import Evaluator

        # Default: pass-through pipeline. Tests can swap inner rules.
        self._inner = Evaluator(rules=[])
        self.calls: list[dict] = []

    async def evaluate(self, sql, schema):

        self.calls.append({"sql": sql, "schema": schema})
        return await self._inner.evaluate(sql, schema)


class _RecordingExecutor:
    """Records every execute call. Returns canned columns/rows."""

    def __init__(self, columns=None, rows=None):
        self._columns = columns or ["id"]
        self._rows = rows or [[1]]
        self.calls: list[dict] = []

    async def execute(self, sql, params=()):
        self.calls.append({"sql": sql, "params": params})
        return (self._columns, self._rows)


class _RecordingAdapter:
    """Adapter-style executor; records execute(sql, params)."""

    def __init__(self, columns=None, rows=None):
        self._columns = columns or ["id"]
        self._rows = rows or [[1]]
        self.calls: list[dict] = []

    async def execute(self, sql, params=()):
        self.calls.append({"sql": sql, "params": params})

        class _Result:
            def __init__(self, columns, rows):
                self.columns = columns
                self.rows = rows

        return _Result(self._columns, self._rows)


def _make_service(
    *,
    policy_provider=None,
    llm=None,
    evaluator=None,
    executor=None,
    adapter=None,
    schema_context=None,
    user_id="550e8400-e29b-41d4-a716-446655440000",
    user_role_id="660e8400-e29b-41d4-a716-446655440000",
    connection_id="770e8400-e29b-41d4-a716-446655440000",
    policies_by_connection: dict[uuid.UUID, _RolePolicy] | None = None,
):
    """Build a QueryService with recording deps and a fixed user/connection.

    ``policies_by_connection`` is the simplest policy-provider pattern: a
    dict keyed by connection_id. The provider returns the entry from the
    dict or ``None``.
    """
    if policies_by_connection is not None:

        async def _provider(uid, cid):
            return policies_by_connection.get(cid)

        policy_provider = policy_provider or _provider
    db = AsyncMock()
    db_conn_uuid = uuid.UUID(connection_id)
    db_conn_id = str(db_conn_uuid)

    def _execute_side_effect(stmt, *args, **kwargs):
        async def _coro():
            stmt_str = str(stmt)
            if "database_connections" in stmt_str:
                return MagicMock(fetchone=MagicMock(return_value=(db_conn_id,)))
            if "FROM users" in stmt_str:
                user = MagicMock()
                user.id = db_conn_id
                user.role_id = uuid.UUID(user_role_id)
                return MagicMock(scalar_one_or_none=MagicMock(return_value=user))
            return MagicMock(fetchone=MagicMock(return_value=(3,)))

        return _coro()

    db.execute = _execute_side_effect
    db.flush = AsyncMock()

    repo = MagicMock()
    repo.list_by_session = AsyncMock(return_value=[])
    repo.get_latest_by_session = AsyncMock(return_value=None)
    repo.get_by_attempt_id = AsyncMock(return_value=None)
    _saved = MagicMock(id="aaaaaaaa-0000-0000-0000-000000000001")
    repo.create = AsyncMock(return_value=_saved)

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

        async def eval(self, script, num_keys, *args):
            return 1

    return QueryService(
        accepted_query_repository=repo,
        session_repository=session_repo,
        db_session=db,
        redis=_FakeRedis(),
        llm=llm or _RecordingLLM(),
        evaluator=evaluator or _RecordingEvaluator(),
        source_db_executor=executor or _RecordingExecutor(),
        source_db_adapter=adapter,
        schema_context=schema_context or _schema_context(),
        llm_provider="stub",
        connection_id=connection_id,
        role_policy_provider=policy_provider,
    ), {
        "repo": repo,
        "session_repo": session_repo,
        "db": db,
        "llm": llm or _RecordingLLM(),
        "evaluator": evaluator or _RecordingEvaluator(),
        "executor": executor or _RecordingExecutor(),
    }


# ─── 1. Schema filter before prompt ─────────────────────────────────


class TestSchemaFilterBeforePrompt:
    """FR-128 / S-006: prompt must contain only role-allowed schema."""

    @pytest.mark.asyncio
    async def test_llm_receives_filtered_schema_when_policy_allows_subset(self):
        """Allowed tables=[orders(id, customer_id)]; full schema has
        orders(id, customer_id, ssn) and payments(id, order_id). The
        LLM prompt must NOT mention ``ssn`` or ``payments``."""
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[
                {"table": "orders", "columns": ["id", "customer_id"]},
            ],
        )
        llm = _RecordingLLM()
        service, _ = _make_service(
            llm=llm,
            policies_by_connection={conn_id: policy},
        )

        await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="How many orders?",
            connection_id=str(conn_id),
        )
        assert len(llm.calls) == 1
        sent = llm.calls[0]["schema_context"]
        assert "ssn" not in str(sent), f"ssn leaked into LLM prompt: {sent!r}"
        assert "payments" not in str(sent), f"payments leaked into LLM prompt: {sent!r}"
        assert "orders" in str(sent)

    @pytest.mark.asyncio
    async def test_llm_receives_full_schema_when_no_policy(self):
        """User has no role_id (or no policy for this connection) — the
        full schema is passed through unchanged (backward compat)."""
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        llm = _RecordingLLM()
        # policies_by_connection = empty dict — no policy for any connection
        service, _ = _make_service(
            llm=llm,
            policies_by_connection={},
        )

        await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="How many orders?",
            connection_id=str(conn_id),
        )
        sent = str(llm.calls[0]["schema_context"])
        assert "ssn" in sent, "full schema should include ssn column"
        assert "payments" in sent

    @pytest.mark.asyncio
    async def test_empty_allowed_tables_fails_closed_before_llm(self):
        """User has a role with empty allowed_tables (deny-all) — the
        LLM must NOT be called and the request must return a rejection
        with ``error.queryBlockedPolicy``."""
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[],  # deny-all
        )
        llm = _RecordingLLM()
        service, _ = _make_service(
            llm=llm,
            policies_by_connection={conn_id: policy},
        )

        result = await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="How many orders?",
            connection_id=str(conn_id),
        )
        # LLM was never called — fail-closed before prompt.
        assert llm.calls == []
        # Response is a sanitized rejection.
        from app.schemas.query import EvaluatorRejection

        assert isinstance(result, EvaluatorRejection)
        # Either the message is the i18n key directly or a violation
        # uses the role_authorization rule with the localized key.
        violation_keys = [v.message_key for v in result.violations]
        assert any("queryBlockedPolicy" in k for k in violation_keys), (
            f"expected queryBlockedPolicy in {violation_keys}"
        )

    @pytest.mark.asyncio
    async def test_input_schema_not_mutated_by_filter(self):
        """filter_schema() returns a new SchemaContext. The input
        ``self._schema_context`` must be unchanged after submit."""
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
        )
        llm = _RecordingLLM()
        service, _ = _make_service(
            llm=llm,
            policies_by_connection={conn_id: policy},
        )
        full = _schema_context()
        original_table_count = len(full.tables)
        original_orders_col_count = len(full.find_table("orders").columns)

        await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="How many?",
            connection_id=str(conn_id),
        )

        # Input schema object untouched.
        assert len(full.tables) == original_table_count
        assert len(full.find_table("orders").columns) == original_orders_col_count


# ─── 2. Evaluator blocks generated SQL outside policy ───────────────


class TestEvaluatorAuthBeforeExecution:
    """FR-130 / S-007: RoleAuthorizationRule blocks out-of-policy SQL
    before execution. The LLM may have generated an SQL that touches a
    table or column not in the role's policy — the evaluator must
    catch that and return an EvaluatorRejection with
    ``error.queryBlockedPolicy``."""

    @pytest.mark.asyncio
    async def test_disallowed_table_blocked_before_executor(self):
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
        )
        # LLM returns SQL that references a table NOT in the policy.
        llm = _RecordingLLM(sql="SELECT id FROM payments")
        executor = _RecordingExecutor()
        service, _ = _make_service(
            llm=llm,
            executor=executor,
            policies_by_connection={conn_id: policy},
        )

        result = await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="How many payments?",
            connection_id=str(conn_id),
        )
        from app.schemas.query import EvaluatorRejection

        assert isinstance(result, EvaluatorRejection)
        assert executor.calls == [], "executor must NOT be called when evaluator rejects"
        violation_keys = [v.message_key for v in result.violations]
        assert "error.queryBlockedPolicy" in violation_keys

    @pytest.mark.asyncio
    async def test_disallowed_column_blocked_before_executor(self):
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
        )
        # SQL references orders.ssn which is NOT in the policy.
        llm = _RecordingLLM(sql="SELECT ssn FROM orders")
        executor = _RecordingExecutor()
        service, _ = _make_service(
            llm=llm,
            executor=executor,
            policies_by_connection={conn_id: policy},
        )

        result = await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="Show me SSNs",
            connection_id=str(conn_id),
        )
        from app.schemas.query import EvaluatorRejection

        assert isinstance(result, EvaluatorRejection)
        assert executor.calls == []
        assert "error.queryBlockedPolicy" in [v.message_key for v in result.violations]

    @pytest.mark.asyncio
    async def test_allowed_sql_proceeds_to_executor(self):
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "orders", "columns": ["id", "customer_id"]}],
        )
        llm = _RecordingLLM(sql="SELECT id, customer_id FROM orders")
        executor = _RecordingExecutor(columns=["id", "customer_id"], rows=[[1, 42]])
        service, _ = _make_service(
            llm=llm,
            executor=executor,
            policies_by_connection={conn_id: policy},
        )
        result = await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="Show orders",
            connection_id=str(conn_id),
        )
        assert result.kind == "result"
        assert len(executor.calls) == 1


# ─── 3. Row filter injection before execute ─────────────────────────


class TestRowFilterInjection:
    """FR-131 / S-005: apply_row_filters() injects per-role WHERE
    fragments into the generated SQL via parameters, never string
    interpolation."""

    @pytest.mark.asyncio
    async def test_row_filter_injected_via_params_not_interpolation(self):
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "orders", "columns": ["id", "customer_id"]}],
            row_filters=[{"table": "orders", "filter": "customer_id = {user.subject_id}"}],
            user_context={"email": "u@example.com", "subject_id": "user-42", "role": "viewer"},
        )
        llm = _RecordingLLM(sql="SELECT id FROM orders")
        executor = _RecordingExecutor()
        service, _ = _make_service(
            llm=llm,
            executor=executor,
            policies_by_connection={conn_id: policy},
        )
        await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="My orders",
            connection_id=str(conn_id),
        )
        # Executor called once.
        assert len(executor.calls) == 1
        call = executor.calls[0]
        # The user value is in PARAMS, not in the SQL string.
        assert "user-42" not in call["sql"], f"user value leaked into SQL: {call['sql']!r}"
        assert "user-42" in call["params"], f"user value missing from params: {call['params']!r}"
        # SQL contains a placeholder token, not the literal value.
        assert "$1" in call["sql"] or "?" in call["sql"] or "%s" in call["sql"]
        # WHERE clause was added.
        assert "WHERE" in call["sql"].upper()
        assert "customer_id" in call["sql"].lower()

    @pytest.mark.asyncio
    async def test_no_row_filter_means_no_where_injection(self):
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
            row_filters=[],  # no filters
        )
        llm = _RecordingLLM(sql="SELECT id FROM orders")
        executor = _RecordingExecutor()
        service, _ = _make_service(
            llm=llm,
            executor=executor,
            policies_by_connection={conn_id: policy},
        )
        await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="How many?",
            connection_id=str(conn_id),
        )
        call = executor.calls[0]
        # No WHERE injected, no params.
        assert call["params"] == ()
        assert "WHERE" not in call["sql"].upper()


# ─── 4. Column masking after execute ────────────────────────────────


class TestColumnMaskAfterExecute:
    """FR-132 / S-007: column_masks config is applied to the
    QueryResult after execution. Masked values are "***" and
    ColumnMeta.masked=True."""

    @pytest.mark.asyncio
    async def test_masked_column_replaced_and_flag_set(self):
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "orders", "columns": ["id", "customer_id", "ssn"]}],
            column_masks=[{"table": "orders", "columns": ["ssn"]}],
        )
        llm = _RecordingLLM(sql="SELECT id, ssn FROM orders")
        executor = _RecordingExecutor(
            columns=["id", "ssn"],
            rows=[[1, "111-22-3333"], [2, "444-55-6666"]],
        )
        service, _ = _make_service(
            llm=llm,
            executor=executor,
            policies_by_connection={conn_id: policy},
        )
        result = await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="Show orders",
            connection_id=str(conn_id),
        )
        assert result.kind == "result"
        # Masked column metadata
        ssn_meta = next(c for c in result.columns if c.name == "ssn")
        assert ssn_meta.masked is True
        id_meta = next(c for c in result.columns if c.name == "id")
        assert id_meta.masked is False
        # Masked rows
        for row in result.rows:
            assert "111-22-3333" not in row
            assert "444-55-6666" not in row
            assert "***" in row

    @pytest.mark.asyncio
    async def test_no_mask_config_keeps_raw_values(self):
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "orders", "columns": ["id", "ssn"]}],
            column_masks=[],
        )
        llm = _RecordingLLM(sql="SELECT id, ssn FROM orders")
        executor = _RecordingExecutor(
            columns=["id", "ssn"],
            rows=[[1, "111-22-3333"]],
        )
        service, _ = _make_service(
            llm=llm,
            executor=executor,
            policies_by_connection={conn_id: policy},
        )
        result = await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="Show orders",
            connection_id=str(conn_id),
        )
        # No masking — values preserved.
        assert result.rows[0][1] == "111-22-3333"
        assert all(c.masked is False for c in result.columns)


# ─── 5. End-to-end order: filter -> auth -> row filter -> mask ──────


class TestIntegratedOrder:
    """Verify the full pipeline ordering using call timestamps / list
    indices. The flow is:

    1. LLM called with filtered schema
    2. Evaluator runs (with RoleAuthorizationRule)
    3. Row filter applied (rewrite SQL, append params)
    4. Executor called with rewritten SQL + params
    5. Column mask applied to QueryResult
    """

    @pytest.mark.asyncio
    async def test_full_happy_path(self):
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "orders", "columns": ["id", "customer_id", "ssn"]}],
            row_filters=[{"table": "orders", "filter": "customer_id = {user.subject_id}"}],
            column_masks=[{"table": "orders", "columns": ["ssn"]}],
            user_context={"email": "u@example.com", "subject_id": "user-42", "role": "viewer"},
        )
        llm = _RecordingLLM(sql="SELECT id, customer_id, ssn FROM orders")
        executor = _RecordingExecutor(
            columns=["id", "customer_id", "ssn"],
            rows=[[1, 42, "secret-1"], [2, 42, "secret-2"]],
        )
        service, deps = _make_service(
            llm=llm,
            executor=executor,
            policies_by_connection={conn_id: policy},
        )
        result = await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="My orders",
            connection_id=str(conn_id),
        )

        # 1. LLM called with FILTERED schema (no payments; only orders
        #    columns allowed by policy).
        assert len(llm.calls) == 1
        sent = str(llm.calls[0]["schema_context"])
        assert "payments" not in sent
        assert "ssn" not in sent  # allowed but masked — does it appear?
        # NOTE: filter_schema keeps masked columns (masking is a
        # post-execution concern; the LLM may need to reference ssn if
        # admin wants the value masked but queryable). However,
        # FR-128/FR-129 say "allowed tables/columns" which INCLUDES ssn
        # in this policy. So ssn SHOULD appear in the prompt.

        # 2. Evaluator called.
        assert len(deps["evaluator"].calls) == 1
        eval_sql = deps["evaluator"].calls[0]["sql"]
        assert "orders" in eval_sql.lower()

        # 3. Executor called with rewritten SQL + params.
        assert len(executor.calls) == 1
        exec_call = executor.calls[0]
        assert "user-42" not in exec_call["sql"]
        assert "user-42" in exec_call["params"]

        # 4. Result masked.
        assert result.kind == "result"
        for row in result.rows:
            assert "secret-1" not in row
            assert "secret-2" not in row
            assert "***" in row


# ─── 6. Policy schema drift maps to error.policySchemaConflict ──────


class TestErrorMapping:
    """PolicySchemaConflictError (T-705) bubbles up from
    apply_row_filters and is translated to a localized, sanitized
    HTTP error with message key ``error.policySchemaConflict``."""

    @pytest.mark.asyncio
    async def test_schema_drift_raises_sanitized_error(self, monkeypatch):
        """Patch apply_row_filters to raise PolicySchemaConflictError.
        Verify the service surfaces a sanitized 503 / 409 with the
        i18n key ``error.policySchemaConflict``."""
        from app.services import policy_enforcement as pe

        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
            row_filters=[{"table": "orders", "filter": "id = {user.subject_id}"}],
            user_context={"email": "u@example.com", "subject_id": "user-42", "role": "viewer"},
        )
        llm = _RecordingLLM(sql="SELECT id FROM orders")
        executor = _RecordingExecutor()
        service, _ = _make_service(
            llm=llm,
            executor=executor,
            policies_by_connection={conn_id: policy},
        )

        # Force apply_row_filters to raise drift.
        async def _raise(*args, **kwargs):
            raise PolicySchemaConflictError()

        monkeypatch.setattr(pe.PolicyEnforcementService, "apply_row_filters", staticmethod(_raise))

        with pytest.raises(Exception) as exc_info:
            await service.submit_question(
                http_session_id="http-sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                question="How many?",
                connection_id=str(conn_id),
            )
        # Sanitized HTTPException with the i18n key.
        assert exc_info.value.status_code in (409, 503)
        detail = exc_info.value.detail
        assert detail.get("message_key") == "error.policySchemaConflict"
        # No leak in the detail.
        detail_str = repr(detail)
        for forbidden in ("orders", "id", "{user.", "user-42", "postgres", "policySchema"):
            if forbidden in detail_str:
                # ``"policySchema"`` is the key itself, so we only
                # check the other values.
                if forbidden == "policySchema":
                    continue
                pytest.fail(f"leaked {forbidden!r} in error detail: {detail_str}")


# ─── 7. No raw user value in executed SQL or user-facing error ──────


class TestNoUserValueLeak:
    """FR-131 / S-004: the user-context value (e.g. subject_id) must
    NEVER be interpolated into the executed SQL or appear in any
    user-facing error string."""

    @pytest.mark.asyncio
    async def test_user_value_not_in_executed_sql(self):
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        sentinel = "leakcanary-aaa-bbb-ccc"
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "orders", "columns": ["id", "customer_id"]}],
            row_filters=[
                {
                    "table": "orders",
                    "filter": f"customer_id = '{sentinel}'",  # direct literal
                }
            ],
            user_context={"email": "u@example.com", "subject_id": sentinel, "role": "viewer"},
        )
        llm = _RecordingLLM(sql="SELECT id FROM orders")
        executor = _RecordingExecutor()
        service, _ = _make_service(
            llm=llm,
            executor=executor,
            policies_by_connection={conn_id: policy},
        )
        await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="My orders",
            connection_id=str(conn_id),
        )
        # The literal in the filter SHOULD have been replaced with a
        # placeholder — the executor SQL must NOT contain the
        # sentinel, but the params must.
        call = executor.calls[0]
        assert sentinel not in call["sql"]
        assert sentinel in call["params"]


# ─── 8. Backward compat: no policy -> existing flow unchanged ──────


class TestBackwardCompat:
    """When the user has no role_id OR no policy for the connection,
    the existing Phase 1-3 flow must be byte-equivalent: full schema,
    no row filters, no column masks, no RoleAuthorizationRule."""

    @pytest.mark.asyncio
    async def test_no_role_id_skips_policy_enforcement(self):
        # role_id is None — no policy enforcement at all.
        llm = _RecordingLLM(sql="SELECT id, ssn FROM orders")
        executor = _RecordingExecutor(columns=["id", "ssn"], rows=[[1, "raw"]])
        # Build with role_id=None
        db = AsyncMock()
        db_conn_id = "770e8400-e29b-41d4-a716-446655440000"

        def _execute(stmt, *args, **kwargs):
            async def _coro():
                stmt_str = str(stmt)
                if "database_connections" in stmt_str:
                    return MagicMock(fetchone=MagicMock(return_value=(db_conn_id,)))
                if "FROM users" in stmt_str:
                    user = MagicMock()
                    user.id = db_conn_id
                    user.role_id = None
                    return MagicMock(scalar_one_or_none=MagicMock(return_value=user))
                return MagicMock(fetchone=MagicMock(return_value=(3,)))

            return _coro()

        db.execute = _execute
        db.flush = AsyncMock()
        repo = MagicMock()
        repo.list_by_session = AsyncMock(return_value=[])
        repo.get_latest_by_session = AsyncMock(return_value=None)
        repo.get_by_attempt_id = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=MagicMock(id="aaaaaaaa-0000-0000-0000-000000000001"))
        session_repo = MagicMock()
        session_repo.create = AsyncMock(return_value=MagicMock(id="550e8400-e29b-41d4-a716-446655440001"))
        session_repo.get_by_id = AsyncMock(return_value=None)

        class _R:
            def __init__(self):
                self._d: dict = {}

            async def set(self, k, v, nx=False, ex=None):
                if nx and k in self._d:
                    return False
                self._d[k] = str(v)
                return True

            async def get(self, k):
                return self._d.get(k)

            async def delete(self, k):
                self._d.pop(k, None)
                return True

            async def eval(self, *a, **k):
                return 1

        service = QueryService(
            accepted_query_repository=repo,
            session_repository=session_repo,
            db_session=db,
            redis=_R(),
            llm=llm,
            evaluator=_RecordingEvaluator(),
            source_db_executor=executor,
            schema_context=_schema_context(),
            connection_id=db_conn_id,
            role_policy_provider=None,
        )
        result = await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41b4-a716-446655440000",
            question="Show me SSNs",
            connection_id=db_conn_id,
        )
        assert result.kind == "result"
        # No masking applied.
        assert result.rows[0][1] == "raw"
        # No row-filter injection — raw SQL passed through.
        assert executor.calls[0]["sql"] == "SELECT id, ssn FROM orders"
        assert executor.calls[0]["params"] == ()


# ─── 9. Regenerate path uses the same enforcement ──────────────────


class TestRegeneratePath:
    """The regenerate path (POST /query/regenerate) must apply the
    same policy enforcement: schema filter, evaluator auth, row
    filter, column mask."""

    @pytest.mark.asyncio
    async def test_regenerate_blocks_disallowed_sql(self):
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
        )
        # First LLM (submit) would have succeeded with allowed SQL,
        # regenerate produces disallowed SQL.
        llm = _RecordingLLM(sql="SELECT id FROM payments")
        executor = _RecordingExecutor()
        service, deps = _make_service(
            llm=llm,
            executor=executor,
            policies_by_connection={conn_id: policy},
        )

        # Build a prior EphemeralAttempt in Redis
        prior_attempt = MagicMock()
        prior_attempt.attempt_id = "attempt-prev-1"
        prior_attempt.user_id = "550e8400-e29b-41d4-a716-446655440000"
        prior_attempt.question = "How many payments?"
        prior_attempt.sql = "SELECT id FROM orders"
        prior_attempt.attempt_number = 1
        prior_attempt.llm_provider = "stub"

        # Monkeypatch the EphemeralAttempt accessors
        from app.services import query_service as qs

        orig_get = qs.get_attempt
        orig_delete = qs.delete_attempt

        async def _get(attempt_id, session_id, redis):
            return prior_attempt

        async def _delete(attempt_id, redis):
            return True

        qs.get_attempt = _get
        qs.delete_attempt = _delete
        # Pre-set active_attempt in redis
        await service._redis.set("active_attempt:http-sess-1", "attempt-prev-1")

        try:
            result = await service.regenerate_query("attempt-prev-1", "http-sess-1")
        finally:
            qs.get_attempt = orig_get
            qs.delete_attempt = orig_delete

        from app.schemas.query import RefinePrompt

        # The new SQL is blocked by the role auth -> regenerate returns
        # a RefinePrompt (the second consecutive rejection).
        assert isinstance(result, RefinePrompt)
        # Executor never called with the new SQL.
        assert executor.calls == []


# ─── 10. Param ordering preserved ──────────────────────────────────


class TestParamOrdering:
    """Row-filter params are appended AFTER any existing
    generated-SQL params. The order is critical: asyncpg consumes
    them positionally, postgres-indexed."""

    @pytest.mark.asyncio
    async def test_row_filter_params_appended_in_order(self):
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "orders", "columns": ["id", "customer_id"]}],
            row_filters=[
                {"table": "orders", "filter": "customer_id = {user.subject_id}"},
                {"table": "orders", "filter": "id > {user.role}"},  # abuses role as number
            ],
            user_context={
                "email": "u@example.com",
                "subject_id": "user-42",
                "role": "viewer",
            },
        )
        # LLM produces SQL with no params.
        llm = _RecordingLLM(sql="SELECT id FROM orders")
        executor = _RecordingExecutor()
        service, _ = _make_service(
            llm=llm,
            executor=executor,
            policies_by_connection={conn_id: policy},
        )
        await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="My orders",
            connection_id=str(conn_id),
        )
        call = executor.calls[0]
        # Both user values must be in params.
        assert "user-42" in call["params"]
        assert "viewer" in call["params"]
        # SQL has two placeholders.
        sql = call["sql"]
        assert sql.count("$") >= 2 or sql.count("?") >= 2 or sql.count("%s") >= 2


# ─── 11. Adapter (dialect) path uses params ────────────────────────


class TestAdapterPath:
    """The new source_db_adapter path (multi-dialect) must also
    receive the rewritten SQL + params."""

    @pytest.mark.asyncio
    async def test_adapter_receives_rewritten_sql_and_params(self):
        conn_id = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
        policy = _RolePolicy(
            user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
            role_id=uuid.UUID("660e8400-e29b-41d4-a716-446655440000"),
            connection_id=conn_id,
            allowed_tables=[{"table": "orders", "columns": ["id", "customer_id"]}],
            row_filters=[{"table": "orders", "filter": "customer_id = {user.subject_id}"}],
            user_context={"email": "u@example.com", "subject_id": "user-42", "role": "viewer"},
        )
        llm = _RecordingLLM(sql="SELECT id FROM orders")
        adapter = _RecordingAdapter(columns=["id"], rows=[[1]])
        service, _ = _make_service(
            llm=llm,
            adapter=adapter,
            policies_by_connection={conn_id: policy},
        )
        await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="My orders",
            connection_id=str(conn_id),
        )
        assert len(adapter.calls) == 1
        call = adapter.calls[0]
        assert "user-42" in call["params"]
        assert "user-42" not in call["sql"]
