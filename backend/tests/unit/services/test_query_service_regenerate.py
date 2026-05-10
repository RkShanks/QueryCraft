"""T-112: QueryService regenerate tests.

Tests that regenerate_query behaves like reject (negative context LLM call,
byte-equal detection, max retry, evaluator gate, lock acquire/release).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.attempt_store import EphemeralAttempt
from app.core.exceptions import (
    AttemptNotFound,
    AttemptOwnershipViolation,
)
from app.services.query_service import QueryService


class TestQueryServiceRegenerate:
    """QueryService.regenerate_query tests."""

    @pytest.fixture
    def mock_deps(self):
        """Return mocked dependencies for QueryService."""
        return {
            "repo": MagicMock(),
            "redis": AsyncMock(),
            "llm": MagicMock(),
            "evaluator": AsyncMock(),
            "executor": AsyncMock(),
        }

    @pytest.fixture
    def service(self, mock_deps):
        """Return a QueryService with mocked dependencies."""
        return QueryService(
            accepted_query_repository=mock_deps["repo"],
            redis=mock_deps["redis"],
            llm=mock_deps["llm"],
            evaluator=mock_deps["evaluator"],
            source_db_executor=mock_deps["executor"],
        )

    async def test_regenerate_calls_llm_with_negative_context(self, service, mock_deps):
        """regenerate_query calls LLM with negative context (prior SQL)."""
        prior = EphemeralAttempt(
            attempt_id="a1",
            session_id="s1",
            sql="SELECT 1",
            question="q1",
        )
        mock_deps["llm"].generate_sql = AsyncMock(return_value="SELECT 2")
        mock_deps["evaluator"].evaluate = AsyncMock(return_value=MagicMock(passed=True))
        mock_deps["executor"].execute = AsyncMock(return_value=(["col"], [(1,)]))

        with (
            patch("app.services.query_service.get_attempt", return_value=prior),
            patch("app.services.query_service.store_attempt"),
            patch("app.services.query_service.acquire_lock", return_value=True),
            patch("app.services.query_service.release_lock"),
        ):
            await service.regenerate_query("a1", "s1")

        mock_deps["llm"].generate_sql.assert_awaited_once()
        call_args = mock_deps["llm"].generate_sql.call_args
        assert "SELECT 1" in str(call_args)

    async def test_regenerate_byte_equal_returns_refine_prompt(self, service, mock_deps):
        """Inv 4: if LLM returns same SQL byte-for-byte -> RefinePrompt, no evaluator/executor."""
        prior = EphemeralAttempt(
            attempt_id="a1",
            session_id="s1",
            sql="SELECT 1",
            question="q1",
        )
        mock_deps["llm"].generate_sql = AsyncMock(return_value="SELECT 1")

        with (
            patch("app.services.query_service.get_attempt", return_value=prior),
            patch("app.services.query_service.acquire_lock", return_value=True),
            patch("app.services.query_service.release_lock"),
        ):
            result = await service.regenerate_query("a1", "s1")

        # Byte-equal -> RefinePrompt
        assert result.kind == "refine"
        mock_deps["evaluator"].evaluate.assert_not_called()
        mock_deps["executor"].execute.assert_not_called()

    async def test_regenerate_max_retries_returns_refine_prompt(self, service, mock_deps):
        """On max retries (attempt #2 already), regenerate returns RefinePrompt."""
        prior = EphemeralAttempt(
            attempt_id="a1",
            session_id="s1",
            sql="SELECT 1",
            question="q1",
            attempt_number=2,
        )
        mock_deps["llm"].generate_sql = AsyncMock(return_value="SELECT 2")
        mock_deps["evaluator"].evaluate = AsyncMock(return_value=MagicMock(passed=True))
        mock_deps["executor"].execute = AsyncMock(return_value=(["col"], [(1,)]))

        with (
            patch("app.services.query_service.get_attempt", return_value=prior),
            patch("app.services.query_service.store_attempt"),
            patch("app.services.query_service.acquire_lock", return_value=True),
            patch("app.services.query_service.release_lock"),
        ):
            result = await service.regenerate_query("a1", "s1")

        assert result.kind == "refine"

    async def test_regenerate_evaluator_fail_returns_response_with_result(self, service, mock_deps):
        """On evaluator failure on regenerated SQL, response has evaluator_result (not raised)."""
        prior = EphemeralAttempt(
            attempt_id="a1",
            session_id="s1",
            sql="SELECT 1",
            question="q1",
            attempt_number=1,
        )
        mock_deps["llm"].generate_sql = AsyncMock(return_value="SELECT 2")

        eval_result = MagicMock()
        eval_result.passed = False
        eval_result.violations = [
            MagicMock(rule_name="read_only", message_key="evaluator.violation.dataModifying"),
        ]
        mock_deps["evaluator"].evaluate = AsyncMock(return_value=eval_result)

        with (
            patch("app.services.query_service.get_attempt", return_value=prior),
            patch("app.services.query_service.store_attempt"),
            patch("app.services.query_service.acquire_lock", return_value=True),
            patch("app.services.query_service.release_lock"),
        ):
            result = await service.regenerate_query("a1", "s1")

        # Evaluator fail should return response, not raise
        assert result.kind == "refine"
        mock_deps["executor"].execute.assert_not_called()

    async def test_regenerate_executor_only_on_evaluator_pass(self, service, mock_deps):
        """Inv 1: executor only called if evaluator passes."""
        prior = EphemeralAttempt(
            attempt_id="a1",
            session_id="s1",
            sql="SELECT 1",
            question="q1",
            attempt_number=1,
        )
        mock_deps["llm"].generate_sql = AsyncMock(return_value="SELECT 2")
        mock_deps["evaluator"].evaluate = AsyncMock(return_value=MagicMock(passed=True))
        mock_deps["executor"].execute = AsyncMock(return_value=(["col"], [(1,)]))

        with (
            patch("app.services.query_service.get_attempt", return_value=prior),
            patch("app.services.query_service.store_attempt"),
            patch("app.services.query_service.acquire_lock", return_value=True),
            patch("app.services.query_service.release_lock"),
        ):
            result = await service.regenerate_query("a1", "s1")

        mock_deps["evaluator"].evaluate.assert_awaited_once()
        mock_deps["executor"].execute.assert_awaited_once()
        assert result.kind == "result"

    async def test_regenerate_raises_on_cross_session(self, service, mock_deps):
        """regenerate_query with wrong session raises AttemptOwnershipViolation."""
        async def _get_attempt(aid, sid, redis):
            raise AttemptOwnershipViolation()

        with (
            patch("app.services.query_service.acquire_lock", return_value=True),
            patch("app.services.query_service.release_lock"),
            patch("app.services.query_service.get_attempt", side_effect=_get_attempt),
            pytest.raises(AttemptOwnershipViolation),
        ):
            await service.regenerate_query("a1", "s2")

    async def test_regenerate_raises_on_missing_attempt(self, service, mock_deps):
        """regenerate_query with nonexistent attempt raises AttemptNotFound."""
        async def _get_attempt(aid, sid, redis):
            raise AttemptNotFound()

        with (
            patch("app.services.query_service.acquire_lock", return_value=True),
            patch("app.services.query_service.release_lock"),
            patch("app.services.query_service.get_attempt", side_effect=_get_attempt),
            pytest.raises(AttemptNotFound),
        ):
            await service.regenerate_query("missing", "s1")

    async def test_regenerate_acquires_and_releases_lock(self, service, mock_deps):
        """Processing lock is acquired and released around regenerate."""
        lock_calls = []

        async def _acquire(sid, redis, ttl=60):
            lock_calls.append("acquire")
            return True

        async def _release(sid, redis):
            lock_calls.append("release")

        prior = EphemeralAttempt(
            attempt_id="a1",
            session_id="s1",
            sql="SELECT 1",
            question="q1",
        )
        mock_deps["llm"].generate_sql = AsyncMock(return_value="SELECT 2")
        mock_deps["evaluator"].evaluate = AsyncMock(return_value=MagicMock(passed=True))
        mock_deps["executor"].execute = AsyncMock(return_value=(["col"], [(1,)]))

        with (
            patch("app.services.query_service.get_attempt", return_value=prior),
            patch("app.services.query_service.store_attempt"),
            patch("app.services.query_service.acquire_lock", side_effect=_acquire),
            patch("app.services.query_service.release_lock", side_effect=_release),
        ):
            await service.regenerate_query("a1", "s1")

        assert lock_calls == ["acquire", "release"]

    async def test_regenerate_timeout_error_raises_504_and_releases_lock(self, service, mock_deps):
        """O-003: asyncio.TimeoutError from executor must be caught and return 504, releasing lock."""
        prior = EphemeralAttempt(
            attempt_id="a1",
            session_id="s1",
            sql="SELECT 1",
            question="q1",
            attempt_number=1,
        )
        mock_deps["llm"].generate_sql = AsyncMock(return_value="SELECT 2")
        mock_deps["evaluator"].evaluate = AsyncMock(return_value=MagicMock(passed=True))
        mock_deps["executor"].execute = AsyncMock(side_effect=asyncio.TimeoutError())

        lock_calls = []

        async def _acquire(sid, redis, ttl=60):
            lock_calls.append("acquire")
            return True

        async def _release(sid, redis):
            lock_calls.append("release")

        with (
            patch("app.services.query_service.get_attempt", return_value=prior),
            patch("app.services.query_service.store_attempt"),
            patch("app.services.query_service.acquire_lock", side_effect=_acquire),
            patch("app.services.query_service.release_lock", side_effect=_release),
        ):
            with pytest.raises(Exception) as exc_info:
                await service.regenerate_query("a1", "s1")

        assert exc_info.value.status_code == 504
        assert lock_calls == ["acquire", "release"]
