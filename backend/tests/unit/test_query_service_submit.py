"""Unit tests for QueryService.submit_question (T-050).

Tests: happy path, evaluator failure, LLM error, timeout, concurrent submission,
Redis attempt storage; uses mocked LLM, evaluator, and source-DB.
"""

import builtins
import json
import secrets
from datetime import date, datetime, time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from redis.exceptions import RedisError

from app.evaluator.schema_context import Column, SchemaContext, Table
from app.services.query_service import QueryService, RolePolicy
from tests.lifecycle.helpers import FakeRedis

CONNECTION_ID = "00000000-0000-0000-0000-000000000001"


class _RedactedString(str):
    def __repr__(self) -> str:
        return "<redacted>"


def _sensitive_value() -> _RedactedString:
    return _RedactedString(secrets.token_hex(24))


def _stored_attempt(redis: FakeRedis, attempt_id: str) -> tuple[str, dict]:
    serialized = redis._data[f"attempt:{attempt_id}"]
    return serialized, json.loads(serialized)


def _assert_fragment_absent(fragment: str, serialized: str, channel: str) -> None:
    __tracebackhide__ = True
    if fragment in serialized:
        raise AssertionError(f"sensitive value reached {channel}")


class _ActiveAttemptWriteFailureRedis(FakeRedis):
    def __init__(self, sensitive_fragment: str) -> None:
        super().__init__()
        self._sensitive_fragment = sensitive_fragment
        self.sensitive_write_observed = False

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool | None:
        if self._sensitive_fragment in str(value):
            self.sensitive_write_observed = True
        if key.startswith("active_attempt:"):
            raise RedisError("attempt_state_write_failed")
        return await super().set(key, value, nx=nx, ex=ex)


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
        # Auto-save new methods
        repo.get_by_attempt_id = AsyncMock(return_value=None)
        _saved = MagicMock(id="aaaaaaaa-0000-0000-0000-000000000001")
        repo.create = AsyncMock(return_value=_saved)
        return repo

    @pytest.fixture
    def mock_redis(self):
        return FakeRedis()

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
        # Side-effect to return different values for different SQL queries
        import uuid as _uuid

        _db_conn_id = str(_uuid.UUID(int=0x1))
        # _get_llm_context_cap, _get_max_regenerate_attempts → (3,); _get_database_connection_id → (UUID,)
        # User existence check → returns a user row by default
        call_counter = {"n": 0}

        def _execute_side_effect(stmt, *args, **kwargs):
            call_counter["n"] += 1

            async def _coro():
                stmt_str = str(stmt)
                if "database_connections" in stmt_str:
                    return MagicMock(fetchone=MagicMock(return_value=(_db_conn_id,)))
                if "FROM users" in stmt_str:
                    # User existence check: return a user row by default
                    return MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock(id=_db_conn_id)))
                return MagicMock(fetchone=MagicMock(return_value=(3,)))

            return _coro()

        db.execute = _execute_side_effect
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
            connection_id=CONNECTION_ID,
        )

    @pytest.mark.lifecycle("lock")
    @pytest.mark.asyncio
    async def test_happy_path_returns_query_result(self, service, mock_repo, mock_redis, lifecycle_aware):
        result = await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="Show me something",
        )
        assert result.kind == "result"
        assert result.row_count == 1
        assert result.generated_sql == "SELECT 1 AS id"
        assert result.session_id == "550e8400-e29b-41d4-a716-446655440001"
        set_calls = [c for c in mock_redis._data if c.startswith("processing_lock:") or c.startswith("active_attempt:")]
        assert len(set_calls) >= 1
        # Auto-save: repo.create called with result payload and accepted_query_id returned
        mock_repo.create.assert_awaited()
        create_call = mock_repo.create.await_args
        create_kwargs = create_call[1] if create_call else {}
        assert create_kwargs.get("result_columns") is not None
        assert create_kwargs.get("result_rows") is not None
        assert create_kwargs.get("result_row_count") == 1
        assert result.accepted_query_id == "aaaaaaaa-0000-0000-0000-000000000001"

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
        attempt_keys = [key for key in service._redis._data if key.startswith("attempt:")]
        assert len(attempt_keys) == 1
        assert "executor_result" not in json.loads(service._redis._data[attempt_keys[0]])

    @pytest.mark.asyncio
    async def test_concurrent_submission_raises_409(self, service, mock_redis):
        await mock_redis.set("processing_lock:http-sess-1", "1")
        with pytest.raises(Exception) as exc_info:
            await service.submit_question(
                http_session_id="http-sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                question="Another",
            )
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_submit_stale_user_raises_401(self, service, mock_db_session):
        """Stale Redis session (user not in DB) raises 401, not FK violation 500."""

        async def _no_user(*args, **kwargs):
            return MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        # Override the user existence check to return None (user not found)
        original_side_effect = mock_db_session.execute

        def _stale_user_side_effect(stmt, *args, **kwargs):
            stmt_str = str(stmt)
            if "FROM users" in stmt_str:
                return _no_user()
            return original_side_effect(stmt, *args, **kwargs)

        mock_db_session.execute = _stale_user_side_effect

        with pytest.raises(Exception) as exc_info:
            await service.submit_question(
                http_session_id="http-sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440999",  # non-existent user
                question="Test question",
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.lifecycle("lock")
    @pytest.mark.asyncio
    async def test_chat_session_id_none_creates_new_session(self, service, mock_session_repo, lifecycle_aware):
        """Lazy creation: chat_session_id=None triggers session_repo.create.
        Combined lock + session invariants (T-379).
        """
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

    @pytest.mark.asyncio
    async def test_zero_row_result_does_not_create_result_payload_in_attempt_state(
        self,
        service,
        mock_executor,
        mock_redis,
    ):
        mock_executor.execute.return_value = ([], [])

        response = await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="No matching rows",
        )

        serialized, attempt = _stored_attempt(mock_redis, response.attempt_id)
        assert response.row_count == 0
        assert "executor_result" not in attempt
        assert len(serialized) < 2_048

    @pytest.mark.asyncio
    async def test_non_json_source_values_remain_request_local(
        self,
        service,
        mock_executor,
        mock_redis,
    ):
        sensitive_fragment = _sensitive_value()
        mock_executor.execute.return_value = (
            ["decimal", "datetime", "date", "time", "null", "binary", "unicode", "nested", "protected"],
            [
                [
                    Decimal("10.50"),
                    datetime(2026, 8, 3, 12, 0),
                    date(2026, 8, 3),
                    time(12, 30),
                    None,
                    b"\x00\xff",
                    "مرحبا",
                    {"items": [Decimal("1.25"), None, "قيمة"]},
                    sensitive_fragment,
                ]
            ],
        )

        response = await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="Return typed values",
        )

        serialized, attempt = _stored_attempt(mock_redis, response.attempt_id)
        assert response.row_count == 1
        assert "executor_result" not in attempt
        _assert_fragment_absent(sensitive_fragment, serialized, "Redis attempt state")

    @pytest.mark.asyncio
    async def test_large_result_shape_does_not_expand_attempt_payload(
        self,
        service,
        mock_executor,
        mock_redis,
    ):
        mock_executor.execute.return_value = (
            ["id", "label"],
            [[index, f"row-{index}"] for index in range(2_000)],
        )

        response = await service.submit_question(
            http_session_id="http-sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="Return a large result",
        )

        serialized, attempt = _stored_attempt(mock_redis, response.attempt_id)
        assert response.row_count == 2_000
        assert "executor_result" not in attempt
        assert len(serialized) < 2_048

    @pytest.mark.asyncio
    async def test_malformed_mask_leaves_only_pre_execution_attempt_metadata(
        self,
        service,
        mock_llm,
        mock_executor,
        mock_redis,
    ):
        sensitive_fragment = _sensitive_value()
        connection_uuid = UUID(CONNECTION_ID)

        async def policy_provider(_user_id, _connection_id):
            return RolePolicy(
                user_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                role_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
                connection_id=connection_uuid,
                allowed_tables=[{"table": "orders", "columns": ["id"]}],
                column_masks=[{"table": "orders"}],
            )

        service._role_policy_provider = policy_provider
        service._schema_context = SchemaContext(tables=[Table(name="orders", columns=[Column(name="id")])])
        mock_llm.generate_sql.return_value = "SELECT id FROM orders"
        mock_executor.execute.return_value = (["id"], [[sensitive_fragment]])

        with pytest.raises(ValueError, match="column_mask_config_invalid"):
            await service.submit_question(
                http_session_id="http-sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                question="Malformed mask",
            )

        attempt_keys = [key for key in mock_redis._data if key.startswith("attempt:")]
        assert len(attempt_keys) == 1
        serialized = mock_redis._data[attempt_keys[0]]
        attempt = json.loads(serialized)
        assert attempt["state"] == "EVALUATED"
        assert "executor_result" not in attempt
        _assert_fragment_absent(sensitive_fragment, serialized, "failed attempt state")

    @pytest.mark.asyncio
    async def test_source_failure_keeps_attempt_state_value_free(
        self,
        service,
        mock_executor,
        mock_redis,
    ):
        sensitive_fragment = _sensitive_value()
        mock_executor.execute.side_effect = RuntimeError(sensitive_fragment)

        with pytest.raises(Exception) as exc_info:
            await service.submit_question(
                http_session_id="http-sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                question="Source failure",
            )

        attempt_keys = [key for key in mock_redis._data if key.startswith("attempt:")]
        assert len(attempt_keys) == 1
        serialized = mock_redis._data[attempt_keys[0]]
        assert exc_info.value.status_code == 502
        assert "executor_result" not in json.loads(serialized)
        _assert_fragment_absent(sensitive_fragment, serialized, "failed attempt state")
        _assert_fragment_absent(sensitive_fragment, str(exc_info.value.detail), "API error detail")

    @pytest.mark.asyncio
    async def test_redis_failure_never_receives_source_value(
        self,
        service,
        mock_executor,
        caplog,
    ):
        sensitive_fragment = _sensitive_value()
        redis = _ActiveAttemptWriteFailureRedis(sensitive_fragment)
        service._redis = redis
        mock_executor.execute.return_value = (["protected"], [[sensitive_fragment]])

        with pytest.raises(RedisError) as exc_info:
            await service.submit_question(
                http_session_id="http-sess-1",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                question="Redis failure",
            )

        assert redis.sensitive_write_observed is False
        _assert_fragment_absent(sensitive_fragment, str(exc_info.value), "Redis error")
        _assert_fragment_absent(sensitive_fragment, caplog.text, "logs")
