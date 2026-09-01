"""Unit tests for QueryService.accept_query (T-051).

Tests: accept persists to AcceptedQueryRepository, accept deletes Redis attempt,
accept with expired attempt returns 400, accept with wrong session returns 400.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import get_settings
from app.core.encryption import encrypt
from app.services.query_service import QueryService

CONNECTION_ID = "00000000-0000-0000-0000-000000000001"
ATTEMPT_ID = "550e8400-e29b-41d4-a716-446655440010"
USER_ID = "550e8400-e29b-41d4-a716-446655440000"


def _encrypted_text(text: str, purpose: str) -> str:
    return encrypt(
        json.dumps({"purpose": purpose, "version": 1, "text": text}),
        get_settings().PLATFORM_ENCRYPTION_KEY,
    )


def _attempt_json(*, session_id: str = "sess-1", state: str = "EXECUTED") -> str:
    evaluator_result = None
    if state == "REJECTED":
        evaluator_result = _encrypted_text(
            json.dumps(
                {
                    "passed": False,
                    "violations": [{"rule": "read_only", "message_key": "error.queryBlocked"}],
                }
            ),
            "attempt.evaluator_result",
        )
    return json.dumps(
        {
            "attempt_id": ATTEMPT_ID,
            "session_id": session_id,
            "chat_session_id": None,
            "user_id": USER_ID,
            "database_connection_id": CONNECTION_ID,
            "question": _encrypted_text("Q", "attempt.question"),
            "sql": _encrypted_text("SELECT 1", "attempt.sql"),
            "llm_provider": "ollama",
            "attempt_number": 1,
            "state": state,
            "evaluator_result": evaluator_result,
            "created_at": "",
            "expires_at": "",
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
        mock_query.database_connection_id = CONNECTION_ID
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
        db_session.flush = AsyncMock()
        _db_conn_id = CONNECTION_ID

        def _execute_side_effect(stmt, *args, **kwargs):
            async def _coro():
                stmt_str = str(stmt)
                if "database_connections" in stmt_str:
                    return MagicMock(fetchone=MagicMock(return_value=(_db_conn_id,)))
                if "FROM users" in stmt_str:
                    return MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock(id=_db_conn_id)))
                return MagicMock(fetchone=MagicMock(return_value=(3,)))

            return _coro()

        db_session.execute = _execute_side_effect
        return QueryService(
            accepted_query_repository=mock_repo,
            session_repository=session_repo,
            db_session=db_session,
            redis=mock_redis,
            llm=None,
            evaluator=None,
            source_db_executor=None,
            connection_id=CONNECTION_ID,
        )

    def _make_get(self, active_attempt=ATTEMPT_ID, attempt_data=None):
        async def _get(key):
            if key == "active_attempt:sess-1":
                return active_attempt
            if key == f"attempt:{ATTEMPT_ID}":
                return attempt_data or _attempt_json()
            return None

        return _get

    @pytest.mark.asyncio
    async def test_accept_persists_and_deletes_redis(self, service, mock_repo, mock_redis):
        mock_redis.get.side_effect = self._make_get()
        result = await service.accept_query(
            http_session_id="sess-1",
            user_id=USER_ID,
            attempt_id=ATTEMPT_ID,
        )
        assert result.id == "q-1"
        mock_repo.create.assert_awaited_once()
        mock_redis.delete.assert_awaited()
        assert any(call.args == (f"attempt:{ATTEMPT_ID}",) for call in mock_redis.delete.await_args_list)

    @pytest.mark.asyncio
    async def test_accept_expired_attempt_raises_400(self, service, mock_redis):
        # active_attempt missing means attempt is no longer active
        mock_redis.get.side_effect = self._make_get(active_attempt=None)
        with pytest.raises(Exception) as exc_info:
            await service.accept_query(
                http_session_id="sess-1",
                user_id=USER_ID,
                attempt_id=ATTEMPT_ID,
            )
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_accept_wrong_session_raises_400(self, service, mock_redis):
        mock_redis.get.side_effect = self._make_get(
            active_attempt=ATTEMPT_ID,
            attempt_data=_attempt_json(session_id="sess-2"),
        )
        with pytest.raises(Exception) as exc_info:
            await service.accept_query(
                http_session_id="sess-1",
                user_id=USER_ID,
                attempt_id=ATTEMPT_ID,
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
                user_id=USER_ID,
                attempt_id=ATTEMPT_ID,
            )
        assert exc_info.value.status_code == 409
        mock_repo.create.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_state", ["PENDING", "GENERATED", "EVALUATED", "REJECTED", "TIMEOUT"])
    async def test_accept_invalid_attempt_state_returns_422(self, service, mock_repo, mock_redis, bad_state):
        """O-005: accept_query must only allow EXECUTED attempts."""
        mock_redis.get.side_effect = self._make_get(
            active_attempt=ATTEMPT_ID,
            attempt_data=_attempt_json(state=bad_state),
        )

        with pytest.raises(Exception) as exc_info:
            await service.accept_query(
                http_session_id="sess-1",
                user_id=USER_ID,
                attempt_id=ATTEMPT_ID,
            )
        assert exc_info.value.status_code == 422
        mock_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_accept_stale_user_raises_401(self, service, mock_repo, mock_redis):
        """Accept with stale session user raises 401, not FK 500."""
        mock_redis.get.side_effect = self._make_get()
        # Override db_session to return None for user check
        service._db_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        with pytest.raises(Exception) as exc_info:
            await service.accept_query(
                http_session_id="sess-1",
                user_id=USER_ID,
                attempt_id=ATTEMPT_ID,
            )
        assert exc_info.value.status_code == 401
        mock_repo.create.assert_not_awaited()
