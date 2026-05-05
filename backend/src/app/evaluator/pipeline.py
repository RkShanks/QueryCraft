"""Evaluator pipeline — minimal US-1 stub + new fail-fast pipeline."""

from app.evaluator.base import EvaluatorResult, EvaluatorViolation
from app.evaluator.protocol import EvaluatorRule
from app.evaluator.result import EvaluatorResult as NewEvaluatorResult
from app.evaluator.schema_context import SchemaContext


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


class EvaluatorPipeline:
    """Fail-fast evaluator pipeline.

    Iterates over rules in order; on the first failure returns immediately.
    """

    def __init__(self, rules: list[EvaluatorRule] | None = None):
        self._rules = rules or []

    async def run(self, sql: str, schema: SchemaContext | None = None) -> NewEvaluatorResult:
        """Run all rules against *sql* and return the aggregate result."""
        for rule in self._rules:
            passed, reason = await rule.evaluate(sql, schema)
            if not passed:
                return NewEvaluatorResult(
                    passed=False,
                    failed_rule=rule.name,
                    reason=reason,
                )
        return NewEvaluatorResult(passed=True)
