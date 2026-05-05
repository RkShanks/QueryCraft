"""Unit tests for QueryService.submit_question (T-050).

Tests: happy path, evaluator failure, LLM error, timeout, concurrent submission,
Redis attempt storage; uses mocked LLM, evaluator, and source-DB.
"""

import builtins
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.query_service import QueryService


class TestQueryServiceSubmit:
    """QueryService.submit_question unit tests."""

    @pytest.fixture
    def mock_repo(self):
        return MagicMock()

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.set = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock()
        return redis

    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        llm.generate_sql.return_value = "SELECT 1 AS id"
        return llm

    @pytest.fixture
    def mock_evaluator(self):
        evaluator = AsyncMock()
        evaluator.evaluate.return_value = MagicMock(passed=True, violations=[])
        return evaluator

    @pytest.fixture
    def mock_executor(self):
        executor = AsyncMock()
        executor.execute.return_value = (
            [{"name": "id", "type": "integer"}],
            [[1]],
        )
        return executor

    @pytest.fixture
    def service(self, mock_repo, mock_redis, mock_llm, mock_evaluator, mock_executor):
        return QueryService(mock_repo, mock_redis, mock_llm, mock_evaluator, mock_executor)

    @pytest.mark.asyncio
    async def test_happy_path_returns_query_result(self, service, mock_redis):
        result = await service.submit_question(
            session_id="sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="Show me something",
        )
        assert result.kind == "result"
        assert result.row_count == 1
        assert result.generated_sql == "SELECT 1 AS id"
        assert mock_redis.set.await_count >= 1

    @pytest.mark.asyncio
    async def test_evaluator_failure_returns_rejection(self, service, mock_evaluator):
        violation = MagicMock()
        violation.rule_name = "read_only"
        violation.message_key = "evaluator.violation.dataModifying"
        mock_evaluator.evaluate.return_value = MagicMock(
            passed=False,
            violations=[violation],
        )
        result = await service.submit_question(
            session_id="sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="Bad question",
        )
        assert result.message_key == "query.evaluator.rejected"

    @pytest.mark.asyncio
    async def test_llm_error_raises_502(self, service, mock_llm):
        mock_llm.generate_sql.side_effect = Exception("LLM down")
        with pytest.raises(Exception) as exc_info:
            await service.submit_question(
                session_id="sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                question="Anything",
            )
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_timeout_raises_504(self, service, mock_executor):

        mock_executor.execute.side_effect = builtins.TimeoutError()
        with pytest.raises(Exception) as exc_info:
            await service.submit_question(
                session_id="sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                question="Slow query",
            )
        assert exc_info.value.status_code == 504

    @pytest.mark.asyncio
    async def test_concurrent_submission_raises_409(self, service, mock_redis):
        mock_redis.set.return_value = None  # lock already held (nx failed)
        with pytest.raises(Exception) as exc_info:
            await service.submit_question(
                session_id="sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                question="Another",
            )
        assert exc_info.value.status_code == 409
