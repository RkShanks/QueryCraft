"""Invariant 1: Evaluator gate — no bypass path (T-034).

Submits a question with a mock evaluator returning FAIL and asserts:
1. The evaluator's evaluate() method is awaited with the candidate SQL.
2. The source DB executor is never called.

This test will FAIL if a hypothetical bypass path removes the await
self._evaluator.evaluate(...) call but still returns an EvaluatorRejection,
because the spy assertion requires the call to have happened.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.query_service import QueryService


class TestEvaluatorGate:
    """Evaluator gate integration test."""

    @pytest.mark.asyncio
    async def test_evaluator_fail_never_calls_executor(self, redis_client):
        """If evaluator fails, source DB executor must not be called."""
        llm = AsyncMock()
        llm.generate_sql = AsyncMock(return_value="DELETE FROM customer")
        evaluator = AsyncMock()
        evaluator.evaluate.return_value = MagicMock(
            passed=False,
            violations=[MagicMock(rule_name="read_only", message_key="evaluator.violation.dataModifying")],
        )
        executor = AsyncMock()
        repo = MagicMock()
        repo.list_by_session = AsyncMock(return_value=[])
        user_result = MagicMock(
            scalar_one_or_none=MagicMock(
                return_value=SimpleNamespace(
                    id="550e8400-e29b-41d4-a716-446655440000",
                    username="admin",
                    role_id=None,
                )
            )
        )
        detection_config_result = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        app_config_result = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        db_session = MagicMock()
        db_session.execute = AsyncMock(side_effect=[user_result, detection_config_result, app_config_result])
        db_session.flush = AsyncMock()
        session_repo = MagicMock()
        session_repo.create = AsyncMock(return_value=SimpleNamespace(id="11111111-1111-1111-1111-111111111111"))
        service = QueryService(
            accepted_query_repository=repo,
            session_repository=session_repo,
            db_session=db_session,
            redis=redis_client,
            llm=llm,
            evaluator=evaluator,
            source_db_executor=executor,
        )

        result = await service.submit_question(
            http_session_id="sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="Show customers",
        )
        assert hasattr(result, "message_key")

        # STRONG ASSERTION: evaluator.evaluate must have been awaited with the
        # exact SQL the LLM generated. If a bypass path is introduced that
        # short-circuits the evaluator, this assertion will fail.
        evaluator.evaluate.assert_awaited_once_with("DELETE FROM customer", None)

        # The source DB executor must never be reached.
        executor.execute.assert_not_awaited()
