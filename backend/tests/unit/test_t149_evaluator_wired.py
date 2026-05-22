"""T-149 regression test — Evaluator pipeline must reject unsafe SQL.

Current Evaluator only checks sql.lower().startswith("select"), so
``SELECT pg_sleep(60)`` passes through. After wiring the pipeline with
UnsafePatternRule, pg_sleep must be rejected.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.evaluator.pipeline import Evaluator
from app.evaluator.rules.read_only import ReadOnlyRule
from app.evaluator.rules.schema_validation import SchemaValidationRule
from app.evaluator.rules.single_statement import SingleStatementRule
from app.evaluator.rules.unsafe_pattern import UnsafePatternRule
from app.schemas.query import EvaluatorRejection
from app.services.query_service import QueryService


@pytest.fixture
def mock_deps():
    return {
        "repo": MagicMock(),
        "redis": AsyncMock(),
        "llm": AsyncMock(),
        "executor": AsyncMock(),
    }


@pytest.fixture
def service_with_real_evaluator(mock_deps):
    mock_deps["redis"].set = AsyncMock()
    mock_deps["llm"].generate_sql.return_value = "SELECT pg_sleep(60)"
    mock_deps["executor"].execute.return_value = (
        [{"name": "id", "type": "integer"}],
        [[1]],
    )
    session_repo = MagicMock()
    session_repo.create = AsyncMock(return_value=MagicMock(id="550e8400-e29b-41d4-a716-446655440001"))
    db_session = AsyncMock()
    db_session.execute = AsyncMock(return_value=MagicMock(fetchone=MagicMock(return_value=(3,))))
    db_session.flush = AsyncMock()
    mock_deps["repo"].list_by_session = AsyncMock(return_value=[])
    mock_deps["repo"].get_latest_by_session = AsyncMock(return_value=None)
    return QueryService(
        accepted_query_repository=mock_deps["repo"],
        session_repository=session_repo,
        db_session=db_session,
        redis=mock_deps["redis"],
        llm=mock_deps["llm"],
        evaluator=Evaluator(
            rules=[
                ReadOnlyRule(dialect="postgres"),
                SingleStatementRule(),
                SchemaValidationRule(),
                UnsafePatternRule(),
            ]
        ),
        source_db_executor=mock_deps["executor"],
    )


@pytest.mark.asyncio
async def test_pg_sleep_rejected_by_evaluator(service_with_real_evaluator):
    """SELECT pg_sleep(60) starts with 'select' so naive check passes.
    Wired pipeline must reject it.
    """
    result = await service_with_real_evaluator.submit_question(
        http_session_id="sess-1",
        user_id="550e8400-e29b-41d4-a716-446655440000",
        question="test",
    )
    assert isinstance(result, EvaluatorRejection)
    assert result.violations[0].rule == "unsafe_pattern"
