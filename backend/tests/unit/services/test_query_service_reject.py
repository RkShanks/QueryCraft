"""T-111: QueryService reject tests.

Tests that reject_query triggers auto-retry (same behaviour as regenerate):
negative-context LLM call, byte-equal detection, max retry, evaluator gate,
lock release, and never writes to accepted_queries.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.attempt_store import EphemeralAttempt
from app.core.exceptions import (
    AttemptNotFound,
    AttemptOwnershipViolation,
)
from app.services.query_service import QueryService


def _active_attempt_get(active_attempt="a1"):
    async def _get(key):
        if key == "active_attempt:s1":
            return active_attempt
        return None

    return _get


class TestQueryServiceReject:
    """QueryService.reject_query tests."""

    @pytest.fixture
    def mock_deps(self):
        """Return mocked dependencies for QueryService."""
        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=_active_attempt_get())
        redis.set = AsyncMock()
        redis.delete = AsyncMock()
        session_repo = MagicMock()
        session_repo.create = AsyncMock(return_value=MagicMock(id="550e8400-e29b-41d4-a716-446655440001"))
        session_repo.get_by_id = AsyncMock(return_value=None)
        session_repo.update_last_activity = AsyncMock(return_value=True)
        session_repo.update_preview_text = AsyncMock(return_value=True)
        db_session = AsyncMock()
        db_session.execute = AsyncMock(return_value=MagicMock(fetchone=MagicMock(return_value=(3,))))
        db_session.flush = AsyncMock()
        return {
            "repo": MagicMock(),
            "session_repo": session_repo,
            "db_session": db_session,
            "redis": redis,
            "llm": MagicMock(),
            "evaluator": AsyncMock(),
            "executor": AsyncMock(),
        }

    @pytest.fixture
    def service(self, mock_deps):
        """Return a QueryService with mocked dependencies."""
        mock_deps["repo"].list_by_session = AsyncMock(return_value=[])
        mock_deps["repo"].get_latest_by_session = AsyncMock(return_value=None)
        return QueryService(
            accepted_query_repository=mock_deps["repo"],
            session_repository=mock_deps["session_repo"],
            db_session=mock_deps["db_session"],
            redis=mock_deps["redis"],
            llm=mock_deps["llm"],
            evaluator=mock_deps["evaluator"],
            source_db_executor=mock_deps["executor"],
        )

    @pytest.mark.lifecycle
    async def test_reject_calls_llm_with_negative_context(self, service, mock_deps):
        """reject_query calls LLM with negative context (prior SQL)."""
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
            patch("app.services.query_service.release_lock"),
        ):
            result = await service.reject_query("a1", "s1")

        mock_deps["llm"].generate_sql.assert_awaited_once()
        call_args = mock_deps["llm"].generate_sql.call_args
        assert "SELECT 1" in str(call_args)
        assert result.kind == "result"

    async def test_reject_byte_equal_returns_refine_prompt(self, service, mock_deps):
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
            patch("app.services.query_service.release_lock"),
        ):
            result = await service.reject_query("a1", "s1")

        # Byte-equal -> RefinePrompt
        assert result.kind == "refine"
        mock_deps["evaluator"].evaluate.assert_not_called()
        mock_deps["executor"].execute.assert_not_called()

    async def test_reject_max_retries_returns_refine_prompt(self, service, mock_deps):
        """On max retries (attempt #2 already), reject returns RefinePrompt."""
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
            patch("app.services.query_service.release_lock"),
        ):
            result = await service.reject_query("a1", "s1")

        assert result.kind == "refine"

    async def test_reject_evaluator_fail_returns_refine_prompt(self, service, mock_deps):
        """On evaluator failure on regenerated SQL, returns RefinePrompt."""
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
            patch("app.services.query_service.release_lock"),
        ):
            result = await service.reject_query("a1", "s1")

        assert result.kind == "refine"
        mock_deps["executor"].execute.assert_not_called()

    async def test_reject_executor_only_on_evaluator_pass(self, service, mock_deps):
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
            patch("app.services.query_service.release_lock"),
        ):
            result = await service.reject_query("a1", "s1")

        mock_deps["evaluator"].evaluate.assert_awaited_once()
        mock_deps["executor"].execute.assert_awaited_once()
        assert result.kind == "result"

    async def test_reject_raises_on_cross_session(self, service, mock_deps):
        """reject_query with wrong session raises AttemptOwnershipViolation."""

        async def _get_attempt(aid, sid, redis):
            raise AttemptOwnershipViolation()

        mock_deps["redis"].get = AsyncMock(return_value="a1")
        with (
            patch("app.services.query_service.release_lock"),
            patch("app.services.query_service.get_attempt", side_effect=_get_attempt),
            pytest.raises(AttemptOwnershipViolation),
        ):
            await service.reject_query("a1", "s2")

    async def test_reject_raises_on_missing_attempt(self, service, mock_deps):
        """reject_query with nonexistent attempt raises AttemptNotFound."""

        async def _get_attempt(aid, sid, redis):
            raise AttemptNotFound()

        mock_deps["redis"].get = AsyncMock(return_value="missing")
        with (
            patch("app.services.query_service.release_lock"),
            patch("app.services.query_service.get_attempt", side_effect=_get_attempt),
            pytest.raises(AttemptNotFound),
        ):
            await service.reject_query("missing", "s1")

    async def test_reject_releases_lock(self, service, mock_deps):
        """Processing lock is released around reject."""
        lock_calls = []

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
            patch("app.services.query_service.release_lock", side_effect=_release),
        ):
            await service.reject_query("a1", "s1")

        assert lock_calls == ["release"]

    async def test_reject_never_writes_to_repository(self, service, mock_deps):
        """Reject must never call AcceptedQueryRepository.create."""
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
            patch("app.services.query_service.release_lock"),
        ):
            await service.reject_query("a1", "s1")

        mock_deps["repo"].create.assert_not_called()
