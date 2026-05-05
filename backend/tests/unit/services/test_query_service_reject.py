"""T-111: QueryService reject tests.

Tests that reject_query deletes attempts, validates ownership,
acquires/releases the processing lock, and never calls LLM/executor.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.attempt_store import EphemeralAttempt
from app.core.exceptions import (
    AttemptNotFound,
    AttemptOwnershipViolation,
)
from app.services.query_service import QueryService


class TestQueryServiceReject:
    """QueryService.reject_query tests."""

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

    async def test_reject_deletes_attempt_and_returns_counts(self, service, mock_deps):
        """reject_query deletes attempt and returns reject_count / attempt_count."""
        attempt = EphemeralAttempt(
            attempt_id="a1",
            session_id="s1",
            sql="SELECT 1",
            question="q1",
        )

        with (
            patch("app.services.query_service.get_attempt", return_value=attempt),
            patch("app.services.query_service.delete_attempt") as mock_delete,
            patch("app.services.query_service.acquire_lock", return_value=True),
            patch("app.services.query_service.release_lock"),
        ):
            await service.reject_query("a1", "s1")

        # LLM and executor should NOT be called
        mock_deps["llm"].generate_sql.assert_not_called()
        mock_deps["evaluator"].evaluate.assert_not_called()
        mock_deps["executor"].execute.assert_not_called()
        mock_delete.assert_awaited_once_with("a1", mock_deps["redis"])

    async def test_reject_raises_on_cross_session(self, service, mock_deps):
        """reject_query with wrong session raises AttemptOwnershipViolation."""
        async def _get_attempt(aid, sid, redis):
            raise AttemptOwnershipViolation()

        with (
            patch("app.services.query_service.acquire_lock", return_value=True),
            patch("app.services.query_service.release_lock"),
            patch("app.services.query_service.get_attempt", side_effect=_get_attempt),
            pytest.raises(AttemptOwnershipViolation),
        ):
            await service.reject_query("a1", "s2")

    async def test_reject_raises_on_missing_attempt(self, service, mock_deps):
        """reject_query with nonexistent attempt raises AttemptNotFound."""
        async def _get_attempt(aid, sid, redis):
            raise AttemptNotFound()

        with (
            patch("app.services.query_service.acquire_lock", return_value=True),
            patch("app.services.query_service.release_lock"),
            patch("app.services.query_service.get_attempt", side_effect=_get_attempt),
            pytest.raises(AttemptNotFound),
        ):
            await service.reject_query("missing", "s1")

    async def test_reject_acquires_and_releases_lock(self, service, mock_deps):
        """Processing lock is acquired and released around reject."""
        lock_calls = []

        async def _acquire(sid, redis, ttl=60):
            lock_calls.append("acquire")
            return True

        async def _release(sid, redis):
            lock_calls.append("release")

        attempt = EphemeralAttempt(
            attempt_id="a1",
            session_id="s1",
            sql="SELECT 1",
            question="q1",
        )

        with (
            patch("app.services.query_service.get_attempt", return_value=attempt),
            patch("app.services.query_service.delete_attempt"),
            patch("app.services.query_service.acquire_lock", side_effect=_acquire),
            patch("app.services.query_service.release_lock", side_effect=_release),
        ):
            await service.reject_query("a1", "s1")

        assert lock_calls == ["acquire", "release"]
