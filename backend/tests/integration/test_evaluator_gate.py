"""Invariant 1: Evaluator gate — no bypass path (T-034).

Submits a question with a mock evaluator returning FAIL and asserts the source DB executor is never called.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.query_service import QueryService


class TestEvaluatorGate:
    """Evaluator gate integration test."""

    @pytest.mark.asyncio
    async def test_evaluator_fail_never_calls_executor(self, mock_llm, redis_client):
        """If evaluator fails, source DB executor must not be called."""
        evaluator = AsyncMock()
        evaluator.evaluate.return_value = MagicMock(
            passed=False,
            violations=[MagicMock(rule_name="read_only", message_key="evaluator.violation.dataModifying")],
        )
        executor = AsyncMock()
        repo = MagicMock()
        service = QueryService(repo, redis_client, mock_llm, evaluator, executor)

        result = await service.submit_question(
            session_id="sess-1",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            question="Drop table?",
        )
        assert hasattr(result, "message_key")
        executor.execute.assert_not_awaited()
