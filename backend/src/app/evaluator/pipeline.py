"""Evaluator pipeline — minimal US-1 stub."""

from app.evaluator.base import EvaluatorResult, EvaluatorViolation


class Evaluator:
    """Minimal evaluator that rejects non-SELECT statements."""

    async def evaluate(self, sql: str, schema: None = None) -> EvaluatorResult:
        """Check SQL safety."""
        stripped = sql.strip().lower()
        if not stripped.startswith("select"):
            return EvaluatorResult(
                passed=False,
                violations=[
                    EvaluatorViolation(
                        rule_name="read_only",
                        message_key="evaluator.violation.dataModifying",
                    )
                ],
            )
        return EvaluatorResult(passed=True)
