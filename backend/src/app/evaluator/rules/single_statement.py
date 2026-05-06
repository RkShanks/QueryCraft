"""SingleStatementRule — rejects multi-statement SQL."""

import sqlglot

from app.evaluator.schema_context import SchemaContext


class SingleStatementRule:
    """Evaluator rule that allows only a single SQL statement."""

    name = "single_statement"

    async def evaluate(self, sql: str, schema: SchemaContext | None) -> tuple[bool, str | None]:
        """Reject SQL containing more than one statement."""
        try:
            parsed = sqlglot.parse(sql, read="postgres")
        except Exception:
            return False, "Unable to parse SQL"

        if not parsed or len(parsed) != 1 or parsed[0] is None:
            return False, "Expected exactly one SQL statement"

        return True, None
