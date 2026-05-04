"""Unit tests for QueryService.accept_query (T-051).

Tests: accept persists to AcceptedQueryRepository, accept deletes Redis attempt,
accept with expired attempt returns 400, accept with wrong session returns 400.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.query_service import QueryService


class TestQueryServiceAccept:
    """QueryService.accept_query unit tests."""

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        mock_query = MagicMock()
        mock_query.id = "q-1"
        mock_query.question_text = "Q"
        mock_query.generated_sql = "SELECT 1"
        mock_query.accepted_at = MagicMock()
        mock_query.accepted_at.isoformat.return_value = "2026-05-04T12:00:00Z"
        repo.create = AsyncMock(return_value=mock_query)
        return repo

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock()
        return redis

    @pytest.fixture
    def service(self, mock_repo, mock_redis):
        return QueryService(
            accepted_query_repository=mock_repo,
            redis=mock_redis,
            llm=None,
            evaluator=None,
            source_db_executor=None,
        )

    @pytest.mark.asyncio
    async def test_accept_persists_and_deletes_redis(self, service, mock_repo, mock_redis):
        mock_redis.get.return_value = json.dumps({
            "attempt_id": "a-1",
            "session_id": "sess-1",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "question_text": "Q",
            "generated_sql": "SELECT 1",
            "llm_provider": "ollama",
            "attempt_number": 1,
            "rejected_sqls": [],
        })
        result = await service.accept_query(
            session_id="sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            attempt_id="a-1",
            database_connection_id="550e8400-e29b-41d4-a716-446655440001",
        )
        assert result.id == "q-1"
        mock_repo.create.assert_awaited_once()
        mock_redis.delete.assert_awaited_once_with("attempt:a-1")

    @pytest.mark.asyncio
    async def test_accept_expired_attempt_raises_400(self, service, mock_redis):
        mock_redis.get.return_value = None
        with pytest.raises(Exception) as exc_info:
            await service.accept_query(
                session_id="sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                attempt_id="a-1",
                database_connection_id="550e8400-e29b-41d4-a716-446655440001",
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_accept_wrong_session_raises_400(self, service, mock_redis):
        mock_redis.get.return_value = json.dumps({
            "attempt_id": "a-1",
            "session_id": "sess-2",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "question_text": "Q",
            "generated_sql": "SELECT 1",
            "llm_provider": "ollama",
        })
        with pytest.raises(Exception) as exc_info:
            await service.accept_query(
                session_id="sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                attempt_id="a-1",
                database_connection_id="550e8400-e29b-41d4-a716-446655440001",
            )
        assert exc_info.value.status_code == 400
