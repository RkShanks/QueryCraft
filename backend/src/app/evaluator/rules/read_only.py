"""ReadOnlyRule — rejects any non-SELECT SQL."""

import sqlglot
from sqlglot import exp

from app.evaluator.schema_context import SchemaContext


class ReadOnlyRule:
    """Evaluator rule that allows only SELECT statements (including CTEs)."""

    name = "read_only"

    async def evaluate(self, sql: str, schema: SchemaContext | None) -> tuple[bool, str | None]:
        """Reject SQL containing INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE."""
        try:
            parsed = sqlglot.parse(sql, read="postgres")
        except Exception:
            return False, "Unable to parse SQL"

        if not parsed:
            return False, "Empty SQL"

        for statement in parsed:
            if not isinstance(statement, exp.Select):
                return False, f"Non-SELECT statement: {statement.__class__.__name__}"

            for cte in statement.find_all(exp.CTE):
                if not isinstance(cte.this, exp.Select):
                    return False, f"Non-SELECT CTE: {cte.this.__class__.__name__}"

        return True, None
