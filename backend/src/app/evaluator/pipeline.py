"""Evaluator pipeline — minimal US-1 stub + new fail-fast pipeline."""

from app.evaluator.base import EvaluatorResult, EvaluatorViolation
from app.evaluator.protocol import EvaluatorRule
from app.evaluator.result import EvaluatorResult as NewEvaluatorResult
from app.evaluator.schema_context import SchemaContext

# Map pipeline failed_rule names to i18n message keys.
_MESSAGE_KEY_MAP = {
    "read_only": "evaluator.violation.dataModifying",
    "single_statement": "evaluator.violation.multiStatement",
    "schema_validation": "evaluator.violation.unknownTable",
    "unsafe_pattern": "evaluator.violation.unsafePattern",
}


class Evaluator:
    """Evaluator gate.

    When *rules* are provided, delegates to ``EvaluatorPipeline`` and
    translates the result back to the legacy ``EvaluatorResult`` format.
    Otherwise falls back to the naive ``startswith('select')`` check.
    """

    def __init__(self, rules: list[EvaluatorRule] | None = None):
        self._rules = rules or []
        self._pipeline = EvaluatorPipeline(rules) if rules else None

    async def evaluate(self, sql: str, schema: SchemaContext | None = None) -> EvaluatorResult:
        """Check SQL safety."""
        if self._pipeline is not None:
            pipeline_result = await self._pipeline.run(sql, schema)
            if not pipeline_result.passed:
                msg_key = _MESSAGE_KEY_MAP.get(
                    pipeline_result.failed_rule,
                    "evaluator.violation.unsafePattern",
                )
                return EvaluatorResult(
                    passed=False,
                    violations=[
                        EvaluatorViolation(
                            rule_name=pipeline_result.failed_rule,
                            message_key=msg_key,
                        )
                    ],
                )
            return EvaluatorResult(passed=True)

        # Naive fallback (legacy US-1 behaviour)
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
