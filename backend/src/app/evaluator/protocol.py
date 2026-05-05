"""EvaluatorRule protocol definition."""

from typing import Protocol, runtime_checkable

from app.evaluator.schema_context import SchemaContext


@runtime_checkable
class EvaluatorRule(Protocol):
    """Protocol for evaluator rules.

    Each rule must have a ``name`` attribute and an ``evaluate`` coroutine
    that receives the SQL string and a ``SchemaContext`` and returns a
    ``(passed, reason)`` tuple.
    """

    name: str

    async def evaluate(self, sql: str, schema: SchemaContext | None) -> tuple[bool, str | None]:
        """Evaluate *sql* against this rule.

        Returns:
            (True, None) if the SQL passes the rule.
            (False, reason) if the SQL violates the rule.
        """
        ...
