"""EmptySqlRule — rejects empty or whitespace-only SQL."""

from app.evaluator.schema_context import SchemaContext


class EmptySqlRule:
    """Evaluator rule that rejects empty, whitespace-only, or None SQL."""

    name = "empty_sql"

    async def evaluate(self, sql: str | None, schema: SchemaContext | None) -> tuple[bool, str | None]:
        """Reject SQL that is None or empty/whitespace after stripping."""
        if sql is None or sql.strip() == "":
            return False, "Empty SQL"
        return True, None
