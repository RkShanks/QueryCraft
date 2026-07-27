"""F-003: QueryService passes schema_context to LLM."""

import uuid as _uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.query_service import QueryService

_DB_CONN_ID = str(_uuid.UUID(int=0x1))


class StubLLM:
    """Records the arguments passed to generate_sql."""

    def __init__(self):
        self.calls = []

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
        return "SELECT 1"


class StubEvaluator:
    async def evaluate(self, sql, schema):
        from app.evaluator.base import EvaluatorResult

        return EvaluatorResult(passed=True)


class StubExecutor:
    async def execute(self, sql, *args, **kwargs):
        return (["col"], [[1]])


class StubRepo:
    async def list_by_session(self, *args, **kwargs):
        return []

    async def get_latest_by_session(self, *args, **kwargs):
        return None

    async def get_by_attempt_id(self, *args, **kwargs):
        return None

    async def create(self, **kwargs):
        m = MagicMock()
        m.id = "aaaaaaaa-0000-0000-0000-000000000001"
        return m


class TopSqlStubLLM:
    async def generate_sql(self, **kwargs):
        return "SELECT TOP 5 * FROM SalesLT.Customer"


class MssqlResultAdapter:
    async def execute(self, sql, params):
        return MagicMock(
            columns=[{"name": "CustomerID", "type": "int"}],
            rows=[[1]],
        )


class FakeRedis:
    async def set(self, key, value, nx=False, ex=None):
        return True

    async def get(self, key):
        return None

    async def delete(self, key):
        pass

    async def eval(self, script, num_keys, *args):
        return 1


def _make_db_session():
    """AsyncMock db_session that routes execute() by SQL content."""
    db = AsyncMock()

    def _execute_side_effect(stmt, *args, **kwargs):
        async def _coro():
            stmt_str = str(stmt)
            if "database_connections" in stmt_str:
                return MagicMock(fetchone=MagicMock(return_value=(_DB_CONN_ID,)))
            if "FROM users" in stmt_str:
                return MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock(id=_DB_CONN_ID)))
            return MagicMock(fetchone=MagicMock(return_value=(3,)))

        return _coro()

    db.execute = _execute_side_effect
    db.flush = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_submit_question_passes_schema_context():
    llm = StubLLM()

    session_repo = MagicMock()
    session_repo.create = AsyncMock(return_value=MagicMock(id="550e8400-e29b-41d4-a716-446655440001"))
    session_repo.get_by_id = AsyncMock(return_value=None)
    db_session = _make_db_session()

    service = QueryService(
        accepted_query_repository=StubRepo(),
        session_repository=session_repo,
        db_session=db_session,
        redis=FakeRedis(),
        llm=llm,
        evaluator=StubEvaluator(),
        source_db_executor=StubExecutor(),
        schema_context="TABLE customers (id INT, name TEXT)",
    )

    # Bypass the lock by monkeypatching
    async def _acquire(*args, **kwargs):
        return "test-owner"

    async def _release(*args, **kwargs):
        return True

    service._acquire_lock = _acquire
    service._release_lock_if_owned = _release

    await service.submit_question(
        http_session_id="http-session-1",
        user_id="550e8400-e29b-41d4-a716-446655440000",
        question="How many customers?",
        connection_id="550e8400-e29b-41d4-a716-446655440001",
    )
    assert len(llm.calls) == 1
    assert llm.calls[0]["schema_context"] == "TABLE customers (id INT, name TEXT)"


@pytest.mark.asyncio
async def test_tsql_top_query_reaches_adapter_after_evaluator_passes():
    """A valid T-SQL TOP response produces results through the query path."""
    from app.evaluator.pipeline import Evaluator
    from app.evaluator.rules.dialect_validation import DialectValidationRule
    from app.evaluator.rules.empty_sql import EmptySqlRule
    from app.evaluator.rules.read_only import ReadOnlyRule
    from app.evaluator.rules.schema_validation import SchemaValidationRule
    from app.evaluator.rules.single_statement import SingleStatementRule
    from app.evaluator.rules.unsafe_pattern import UnsafePatternRule
    from app.evaluator.schema_context import Column, SchemaContext, Table

    schema_context = SchemaContext(
        tables=[Table(name="SalesLT.Customer", columns=[Column(name="CustomerID", data_type="int")])]
    )
    session_repo = MagicMock()
    session_repo.create = AsyncMock(return_value=MagicMock(id="550e8400-e29b-41d4-a716-446655440001"))
    service = QueryService(
        accepted_query_repository=StubRepo(),
        session_repository=session_repo,
        db_session=_make_db_session(),
        redis=FakeRedis(),
        llm=TopSqlStubLLM(),
        evaluator=Evaluator(
            rules=[
                EmptySqlRule(),
                DialectValidationRule(dialect="tsql"),
                ReadOnlyRule(dialect="tsql"),
                SingleStatementRule(dialect="tsql"),
                SchemaValidationRule(schema_context, dialect="tsql"),
                UnsafePatternRule(dialect="tsql"),
            ]
        ),
        source_db_executor=StubExecutor(),
        source_db_adapter=MssqlResultAdapter(),
        schema_context=schema_context,
        target_dialect="tsql",
    )

    result = await service.submit_question(
        http_session_id="http-session-1",
        user_id="550e8400-e29b-41d4-a716-446655440000",
        question="Show the first customers",
    )

    assert result.kind == "result"
    assert result.generated_sql == "SELECT TOP 5 * FROM SalesLT.Customer"
    assert result.row_count == 1


@pytest.mark.asyncio
async def test_regenerate_query_passes_schema_context():
    llm = StubLLM()
    session_repo = MagicMock()
    db_session = _make_db_session()
    service = QueryService(
        accepted_query_repository=StubRepo(),
        session_repository=session_repo,
        db_session=db_session,
        redis=None,
        llm=llm,
        evaluator=StubEvaluator(),
        source_db_executor=StubExecutor(),
        schema_context="TABLE orders (id INT, total DECIMAL)",
    )

    class FakeRedis:
        async def set(self, key, value, nx=False, ex=None):
            return True

        async def get(self, key):
            return "attempt-1"

        async def delete(self, key):
            pass

        async def eval(self, script, num_keys, *args):
            return 1

    class FakeAttempt:
        attempt_id = "attempt-1"
        session_id = "session-1"
        sql = "SELECT 1"
        question = "How many orders?"
        attempt_number = 1
        llm_provider = "ollama"
        state = "EXECUTED"
        user_id = "550e8400-e29b-41d4-a716-446655440000"

    service._redis = FakeRedis()

    # Monkeypatch get_attempt / delete_attempt
    import app.services.query_service as qs

    orig_get = qs.get_attempt
    orig_delete = qs.delete_attempt

    async def fake_get(attempt_id, session_id, redis):
        return FakeAttempt()

    async def fake_delete(attempt_id, redis):
        pass

    qs.get_attempt = fake_get
    qs.delete_attempt = fake_delete

    import contextlib

    with contextlib.suppress(Exception):
        await service.regenerate_query("attempt-1", "session-1")

    qs.get_attempt = orig_get
    qs.delete_attempt = orig_delete

    assert any(call["schema_context"] == "TABLE orders (id INT, total DECIMAL)" for call in llm.calls)
