"""ReadOnlyRule — rejects any non-SELECT SQL.

T-429: Dialect-aware parsing via sqlglot.parse(sql, read=dialect).
"""

import sqlglot
from sqlglot import exp

from app.db.models.enums import DatabaseType
from app.evaluator.schema_context import SchemaContext

# DatabaseType → sqlglot dialect mapping (T-429, FR-071)
DIALECT_MAP: dict[DatabaseType, str] = {
    DatabaseType.POSTGRESQL: "postgres",
    DatabaseType.MYSQL: "mysql",
    DatabaseType.MSSQL: "tsql",
}


class ReadOnlyRule:
    """Evaluator rule that allows only SELECT statements (including CTEs)."""

    name = "read_only"

    def __init__(self, dialect: str = "postgres") -> None:
        """Initialize with a sqlglot read dialect.

        Args:
            dialect: sqlglot dialect string (e.g. "postgres", "mysql", "tsql").
        """
        self.dialect = dialect

    @classmethod
    def from_database_type(cls, database_type: DatabaseType) -> "ReadOnlyRule":
        """Create a ReadOnlyRule from a DatabaseType enum.

        Args:
            database_type: The database type to map to a sqlglot dialect.

        Returns:
            ReadOnlyRule configured with the appropriate dialect.
        """
        dialect = DIALECT_MAP[database_type]
        return cls(dialect=dialect)

    async def evaluate(self, sql: str, schema: SchemaContext | None) -> tuple[bool, str | None]:
        """Reject SQL containing INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE."""
        try:
            parsed = sqlglot.parse(sql, read=self.dialect)
        except Exception:
            return False, "Unable to parse SQL"

        if not parsed:
            return False, "Empty SQL"

        for statement in parsed:
            result = self._validate_read_only(statement)
            if not result[0]:
                return result

        return True, None

    def _validate_read_only(self, node: exp.Expression) -> tuple[bool, str | None]:
        """Recursively validate that a node and its descendants are read-only."""
        if isinstance(node, (exp.Union, exp.Intersect, exp.Except)):
            left = self._validate_read_only(node.this)
            if not left[0]:
                return left
            right = self._validate_read_only(node.expression)
            if not right[0]:
                return right
            return True, None

        if not isinstance(node, exp.Select):
            return False, f"Non-SELECT statement: {node.__class__.__name__}"

        if node.find(exp.Lock):
            return False, "SELECT with row-level locking is not allowed"

        for cte in node.find_all(exp.CTE):
            cte_result = self._validate_read_only(cte.this)
            if not cte_result[0]:
                return cte_result

        return True, None
