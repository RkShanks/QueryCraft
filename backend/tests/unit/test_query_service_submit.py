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
    def lifecycle_lock_checker(self, mock_redis):
        from tests.lifecycle.invariants import LockInvariant

        return LockInvariant(mock_redis)

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.list_by_session = AsyncMock(return_value=[])
        repo.get_latest_by_session = AsyncMock(return_value=None)
        return repo

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
    def mock_session_repo(self):
        repo = MagicMock()
        repo.create = AsyncMock(return_value=MagicMock(id="550e8400-e29b-41d4-a716-446655440001"))
        repo.get_by_id = AsyncMock(return_value=None)
        repo.update_last_activity = AsyncMock(return_value=True)
        repo.update_preview_text = AsyncMock(return_value=True)
        return repo

    @pytest.fixture
    def mock_db_session(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(fetchone=MagicMock(return_value=(3,))))
        db.flush = AsyncMock()
        return db

    @pytest.fixture
    def service(
        self, mock_repo, mock_session_repo, mock_db_session, mock_redis, mock_llm, mock_evaluator, mock_executor
    ):
        return QueryService(
            accepted_query_repository=mock_repo,
            session_repository=mock_session_repo,
            db_session=mock_db_session,
            redis=mock_redis,
            llm=mock_llm,
            evaluator=mock_evaluator,
            source_db_executor=mock_executor,
        )

    @pytest.mark.lifecycle("lock")
    @pytest.mark.asyncio
    async def test_happy_path_returns_query_result(self, service, mock_redis, lifecycle_aware):
        result = await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="Show me something",
        )
        assert result.kind == "result"
        assert result.row_count == 1
        assert result.generated_sql == "SELECT 1 AS id"
        assert result.session_id == "550e8400-e29b-41d4-a716-446655440001"
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
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="Bad question",
        )
        assert result.message_key == "query.evaluator.rejected"

    @pytest.mark.asyncio
    async def test_llm_error_raises_502(self, service, mock_llm):
        mock_llm.generate_sql.side_effect = Exception("LLM down")
        with pytest.raises(Exception) as exc_info:
            await service.submit_question(
                http_session_id="http-sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                question="Anything",
            )
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_timeout_raises_504(self, service, mock_executor):

        mock_executor.execute.side_effect = builtins.TimeoutError()
        with pytest.raises(Exception) as exc_info:
            await service.submit_question(
                http_session_id="http-sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                question="Slow query",
            )
        assert exc_info.value.status_code == 504

    @pytest.mark.asyncio
    async def test_concurrent_submission_raises_409(self, service, mock_redis):
        mock_redis.set.return_value = None  # lock already held (nx failed)
        with pytest.raises(Exception) as exc_info:
            await service.submit_question(
                http_session_id="http-sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                question="Another",
            )
        assert exc_info.value.status_code == 409

    @pytest.mark.lifecycle("lock")
    @pytest.mark.asyncio
    async def test_chat_session_id_none_creates_new_session(self, service, mock_session_repo, lifecycle_aware):
        """Lazy creation: chat_session_id=None triggers session_repo.create."""
        result = await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="New question",
            chat_session_id=None,
        )
        assert result.kind == "result"
        mock_session_repo.create.assert_awaited_once()
        assert result.session_id == "550e8400-e29b-41d4-a716-446655440001"

    @pytest.mark.asyncio
    async def test_chat_session_id_provided_reuses_existing_session(self, service, mock_session_repo):
        """Follow-up: chat_session_id='existing-id' validates session and skips creation."""
        existing_session = MagicMock()
        existing_session.id = "550e8400-e29b-41d4-a716-446655440002"
        existing_session.preview_text = "Existing preview"
        mock_session_repo.get_by_id.return_value = existing_session

        result = await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="Follow-up",
            chat_session_id="550e8400-e29b-41d4-a716-446655440002",
        )
        assert result.kind == "result"
        assert result.session_id == "550e8400-e29b-41d4-a716-446655440002"
        mock_session_repo.get_by_id.assert_awaited_once()
        mock_session_repo.create.assert_not_awaited()
