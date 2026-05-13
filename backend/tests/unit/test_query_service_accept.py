"""Unit tests for QueryService.accept_query (T-051).

Tests: accept persists to AcceptedQueryRepository, accept deletes Redis attempt,
accept with expired attempt returns 400, accept with wrong session returns 400.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.query_service import QueryService


def _attempt_json():
    return json.dumps(
        {
            "attempt_id": "a-1",
            "session_id": "sess-1",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "question_text": "Q",
            "generated_sql": "SELECT 1",
            "llm_provider": "ollama",
            "attempt_number": 1,
            "rejected_sqls": [],
            "state": "EXECUTED",
        }
    )


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
        mock_repo.list_by_session = AsyncMock(return_value=[])
        mock_repo.get_latest_by_session = AsyncMock(return_value=None)
        mock_repo.get_by_attempt_id = AsyncMock(return_value=None)
        session_repo = MagicMock()
        session_repo.create = AsyncMock(return_value=MagicMock(id="550e8400-e29b-41d4-a716-446655440001"))
        session_repo.get_by_id = AsyncMock(return_value=None)
        session_repo.update_last_activity = AsyncMock(return_value=True)
        session_repo.update_preview_text = AsyncMock(return_value=True)
        db_session = AsyncMock()
        db_session.execute = AsyncMock(return_value=MagicMock(fetchone=MagicMock(return_value=(3,))))
        db_session.flush = AsyncMock()
        return QueryService(
            accepted_query_repository=mock_repo,
            session_repository=session_repo,
            db_session=db_session,
            redis=mock_redis,
            llm=None,
            evaluator=None,
            source_db_executor=None,
        )

    def _make_get(self, active_attempt="a-1", attempt_data=None):
        async def _get(key):
            if key == "active_attempt:sess-1":
                return active_attempt
            if key == "attempt:a-1":
                return attempt_data or _attempt_json()
            return None

        return _get

    @pytest.mark.asyncio
    async def test_accept_persists_and_deletes_redis(self, service, mock_repo, mock_redis):
        mock_redis.get.side_effect = self._make_get()
        result = await service.accept_query(
            http_session_id="sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            attempt_id="a-1",
            database_connection_id="550e8400-e29b-41d4-a716-446655440001",
        )
        assert result.id == "q-1"
        mock_repo.create.assert_awaited_once()
        mock_redis.delete.assert_awaited()
        assert any(call.args == ("attempt:a-1",) for call in mock_redis.delete.await_args_list)

    @pytest.mark.asyncio
    async def test_accept_expired_attempt_raises_400(self, service, mock_redis):
        # active_attempt missing means attempt is no longer active
        mock_redis.get.side_effect = self._make_get(active_attempt=None)
        with pytest.raises(Exception) as exc_info:
            await service.accept_query(
                http_session_id="sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                attempt_id="a-1",
                database_connection_id="550e8400-e29b-41d4-a716-446655440001",
            )
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_accept_wrong_session_raises_400(self, service, mock_redis):
        mock_redis.get.side_effect = self._make_get(
            active_attempt="a-1",
            attempt_data=json.dumps(
                {
                    "attempt_id": "a-1",
                    "session_id": "sess-2",
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "question_text": "Q",
                    "generated_sql": "SELECT 1",
                    "llm_provider": "ollama",
                }
            ),
        )
        with pytest.raises(Exception) as exc_info:
            await service.accept_query(
                http_session_id="sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                attempt_id="a-1",
                database_connection_id="550e8400-e29b-41d4-a716-446655440001",
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_accept_double_accept_race_returns_409(self, service, mock_repo, mock_redis):
        """O-004: second concurrent accept with same attempt_id must return 409."""
        mock_redis.get.side_effect = self._make_get()
        # Simulate lock already held (second caller)
        mock_redis.set.return_value = None

        with pytest.raises(Exception) as exc_info:
            await service.accept_query(
                http_session_id="sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                attempt_id="a-1",
                database_connection_id="550e8400-e29b-41d4-a716-446655440001",
            )
        assert exc_info.value.status_code == 409
        mock_repo.create.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_state", ["PENDING", "GENERATED", "EVALUATED", "REJECTED", "TIMEOUT"])
    async def test_accept_invalid_attempt_state_returns_422(self, service, mock_repo, mock_redis, bad_state):
        """O-005: accept_query must only allow EXECUTED attempts."""
        mock_redis.get.side_effect = self._make_get(
            active_attempt="a-1",
            attempt_data=json.dumps(
                {
                    "attempt_id": "a-1",
                    "session_id": "sess-1",
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "question_text": "Q",
                    "generated_sql": "SELECT 1",
                    "llm_provider": "ollama",
                    "attempt_number": 1,
                    "state": bad_state,
                }
            ),
        )

        with pytest.raises(Exception) as exc_info:
            await service.accept_query(
                http_session_id="sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                attempt_id="a-1",
                database_connection_id="550e8400-e29b-41d4-a716-446655440001",
            )
        assert exc_info.value.status_code == 422
        mock_repo.create.assert_not_called()
