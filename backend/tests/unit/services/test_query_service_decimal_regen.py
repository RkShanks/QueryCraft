"""Regression test for Decimal serialization in regenerate prior_saved path.

When regenerating a query that already has a persisted saved row, the
prior_saved.result_rows assignment must sanitize Decimal values before
storing to PostgreSQL JSONB. This test ensures _sanitize_for_json is
applied in that code path.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.attempt_store import EphemeralAttempt
from app.schemas.query import ColumnMeta
from app.services.query_service import QueryService


def _active_attempt_get(active_attempt="a1"):
    async def _get(key):
        if key == "active_attempt:s1":
            return active_attempt
        return None

    return _get


class TestRegenerateDecimalSerialization:
    """Ensure Decimal values are sanitized in the prior_saved regenerate path."""

    @pytest.fixture
    def mock_deps(self):
        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=_active_attempt_get())
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock()
        redis.eval = AsyncMock(return_value=1)

        session_repo = MagicMock()
        session_repo.create = AsyncMock(return_value=MagicMock(id="550e8400-e29b-41d4-a716-446655440001"))
        session_repo.get_by_id = AsyncMock(return_value=None)
        session_repo.update_last_activity = AsyncMock(return_value=True)
        session_repo.update_preview_text = AsyncMock(return_value=True)

        db_session = AsyncMock()

        def _execute_side_effect(stmt, *args, **kwargs):
            async def _coro():
                stmt_str = str(stmt)
                if "database_connections" in stmt_str:
                    return MagicMock(fetchone=MagicMock(return_value=("00000000-0000-0000-0000-000000000002",)))
                if "FROM users" in stmt_str:
                    return MagicMock(scalar_one_or_none=MagicMock(return_value=MagicMock(id="00000000-0000-0000-0000-000000000001")))
                return MagicMock(fetchone=MagicMock(return_value=(3,)))

            return _coro()

        db_session.execute = _execute_side_effect
        db_session.flush = AsyncMock()

        saved_row = MagicMock(id="aaaaaaaa-0000-0000-0000-000000000001")
        saved_row.session_id = None
        repo = MagicMock()
        # Return a saved row so the prior_saved branch is taken
        repo.get_by_attempt_id = AsyncMock(return_value=saved_row)
        repo.create = AsyncMock(return_value=saved_row)

        return {
            "repo": repo,
            "session_repo": session_repo,
            "db_session": db_session,
            "redis": redis,
            "llm": MagicMock(),
            "evaluator": AsyncMock(),
            "executor": AsyncMock(),
        }

    def _make_service(self, mock_deps):
        return QueryService(
            accepted_query_repository=mock_deps["repo"],
            session_repository=mock_deps["session_repo"],
            db_session=mock_deps["db_session"],
            redis=mock_deps["redis"],
            llm=mock_deps["llm"],
            evaluator=mock_deps["evaluator"],
            source_db_executor=mock_deps["executor"],
            llm_provider="stub",
            schema_context="",
        )

    @pytest.mark.asyncio
    async def test_regenerate_prior_saved_sanitizes_decimal_rows(self, mock_deps):
        """Regenerating an existing saved row must sanitize Decimal values.

        The prior_saved branch (line ~589) assigns result_rows directly.
        If the executor returns Decimal values, they must be converted to
        float before assignment, otherwise PostgreSQL JSONB serialization
        fails with TypeError: Object of type Decimal is not JSON serializable.
        """
        # Setup: prior attempt exists with a saved row
        mock_deps["redis"].get = AsyncMock(side_effect=_active_attempt_get("a1"))

        # Executor returns Decimal values (as PostgreSQL does for numeric/avg)
        decimal_rows = [[Decimal("2.9800000000000000")]]
        mock_deps["executor"].execute = AsyncMock(return_value=(
            [{"name": "avg", "type": "text"}],
            decimal_rows,
        ))
        mock_deps["evaluator"].evaluate = AsyncMock(return_value=MagicMock(violations=[]))
        mock_deps["llm"].generate_sql = AsyncMock(return_value="SELECT AVG(rating) FROM films;")

        # Attempt store get returns a valid attempt
        prior = EphemeralAttempt(
            attempt_id="a1",
            session_id="s1",
            user_id="00000000-0000-0000-0000-000000000001",
            sql="SELECT 1;",
            question="What is the average?",
            attempt_number=1,
            state="EXECUTED",
        )

        service = self._make_service(mock_deps)

        with patch("app.services.query_service.get_attempt", new_callable=AsyncMock, return_value=prior):
            result = await service.regenerate_query("a1", "s1")

        # Verify the prior_saved row was updated with sanitized rows
        saved_row = mock_deps["repo"].get_by_attempt_id.return_value
        assert saved_row.result_rows is not None
        # The rows should be floats, not Decimals
        assert isinstance(saved_row.result_rows[0][0], float)
        assert saved_row.result_rows[0][0] == 2.98
