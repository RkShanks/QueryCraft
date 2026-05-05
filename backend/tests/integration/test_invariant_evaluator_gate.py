"""T-120: Invariant 1 — Evaluator gate (no DB contact on eval failure).

Mocks the evaluator to return FAIL for each of the 4 rules in isolation
and asserts SourceDBExecutor.execute is never called.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.evaluator.base import EvaluatorResult, EvaluatorViolation


class TestInvariantEvaluatorGate:
    """Invariant 1: Evaluator gate integration test."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "rule_name,message_key",
        [
            ("read_only", "evaluator.violation.dataModifying"),
            ("single_statement", "evaluator.violation.multiStatement"),
            ("schema_validation", "evaluator.violation.unknownTable"),
            ("unsafe_pattern", "evaluator.violation.unsafePattern"),
        ],
    )
    async def test_evaluator_fail_never_calls_executor(self, authenticated_client, rule_name, message_key):
        """If evaluator fails, source DB executor must not be called."""
        eval_result = EvaluatorResult(
            passed=False,
            violations=[
                EvaluatorViolation(
                    rule_name=rule_name,
                    message_key=message_key,
                )
            ],
        )

        with (
            patch("app.evaluator.pipeline.Evaluator.evaluate", return_value=eval_result),
            patch("app.source_db.executor.SourceDBExecutor.execute") as mock_execute,
        ):
            response = await authenticated_client.post(
                "/api/v1/query/submit",
                json={"question": "Test question?"},
                headers={"origin": "http://test"},
            )

        assert response.status_code == 422
        data = response.json()
        assert "violations" in data
        assert data["violations"][0]["rule"] == rule_name
        assert data["violations"][0]["message_key"] == message_key
        mock_execute.assert_not_awaited()
