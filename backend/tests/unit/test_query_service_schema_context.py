"""F-003: QueryService passes schema_context to LLM."""

import pytest

from app.services.query_service import QueryService


class StubLLM:
    """Records the arguments passed to generate_sql."""

    def __init__(self):
        self.calls = []

    async def generate_sql(self, question, schema_context, negative_examples=None):
        self.calls.append({
            "question": question,
            "schema_context": schema_context,
            "negative_examples": negative_examples,
        })
        return "SELECT 1"


class StubEvaluator:
    async def evaluate(self, sql, schema):
        from app.evaluator.base import EvaluatorResult
        return EvaluatorResult(passed=True)


class StubExecutor:
    async def execute(self, sql):
        return (["col"], [[1]])


class StubRepo:
    pass


@pytest.mark.asyncio
async def test_submit_question_passes_schema_context():
    llm = StubLLM()
    class FakeRedis:
        async def set(self, key, value, ex=None):
            pass
        async def get(self, key):
            return None
        async def delete(self, key):
            pass

    service = QueryService(
        accepted_query_repository=StubRepo(),
        redis=FakeRedis(),
        llm=llm,
        evaluator=StubEvaluator(),
        source_db_executor=StubExecutor(),
        schema_context="TABLE customers (id INT, name TEXT)",
    )
    # Bypass the lock by monkeypatching
    async def _true(*args, **kwargs):
        return True
    async def _none(*args, **kwargs):
        pass
    service._acquire_lock = _true
    service._release_lock = _none

    await service.submit_question("session-1", "user-1", "How many customers?")
    assert len(llm.calls) == 1
    assert llm.calls[0]["schema_context"] == "TABLE customers (id INT, name TEXT)"


@pytest.mark.asyncio
async def test_regenerate_query_passes_schema_context():
    llm = StubLLM()
    service = QueryService(
        accepted_query_repository=StubRepo(),
        redis=None,
        llm=llm,
        evaluator=StubEvaluator(),
        source_db_executor=StubExecutor(),
        schema_context="TABLE orders (id INT, total DECIMAL)",
    )

    class FakeRedis:
        async def get(self, key):
            return "attempt-1"

        async def delete(self, key):
            pass

    class FakeAttempt:
        attempt_id = "attempt-1"
        session_id = "session-1"
        sql = "SELECT 1"
        question = "How many orders?"
        attempt_number = 1
        llm_provider = "ollama"
        state = "EXECUTED"

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

    assert any(
        call["schema_context"] == "TABLE orders (id INT, total DECIMAL)"
        for call in llm.calls
    )
