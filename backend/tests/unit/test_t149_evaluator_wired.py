"""T-149 regression test — Evaluator pipeline must reject unsafe SQL.

Current Evaluator only checks sql.lower().startswith("select"), so
``SELECT pg_sleep(60)`` passes through. After wiring the pipeline with
UnsafePatternRule, pg_sleep must be rejected.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.evaluator.pipeline import Evaluator
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
    return QueryService(
        mock_deps["repo"],
        mock_deps["redis"],
        mock_deps["llm"],
        Evaluator(),
        mock_deps["executor"],
    )


@pytest.mark.asyncio
async def test_pg_sleep_rejected_by_evaluator(service_with_real_evaluator):
    """SELECT pg_sleep(60) starts with 'select' so naive check passes.
    Wired pipeline must reject it.
    """
    result = await service_with_real_evaluator.submit_question(
        session_id="sess-1",
        user_id="user-1",
        question="test",
    )
    assert isinstance(result, EvaluatorRejection)
    assert result.violations[0].rule_name == "unsafe_pattern"
