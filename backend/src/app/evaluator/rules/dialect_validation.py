"""DialectValidationRule — validates SQL can be parsed for the target dialect.

T-430, FR-071, FR-092: Rejects SQL that fails dialect parsing.
Parse failure triggers regeneration with explicit dialect hint.
Never execute unvalidated SQL.
"""

import sqlglot

from app.db.models.enums import DatabaseType
from app.evaluator.rules.read_only import DIALECT_MAP
from app.evaluator.schema_context import SchemaContext


class DialectValidationRule:
    """Evaluator rule that validates SQL can be parsed for the target dialect."""

    name = "dialect_validation"

    def __init__(self, dialect: str) -> None:
        """Initialize with a sqlglot read dialect.

        Args:
            dialect: sqlglot dialect string (e.g. "postgres", "mysql", "tsql").
        """
        self.dialect = dialect

    @classmethod
    def from_database_type(cls, database_type: DatabaseType) -> "DialectValidationRule":
        """Create a DialectValidationRule from a DatabaseType enum."""
        dialect = DIALECT_MAP[database_type]
        return cls(dialect=dialect)

    async def evaluate(self, sql: str, schema: SchemaContext | None) -> tuple[bool, str | None]:
        """Validate SQL parses correctly for the target dialect.

        Returns:
            (True, None) if SQL parses successfully.
            (False, reason) if SQL fails to parse or is empty.
        """
        if not sql or not sql.strip():
            return False, f"Empty SQL for dialect '{self.dialect}'"

        # T-SQL uses TOP, not LIMIT. Reject LIMIT syntax for tsql dialect.
        if self.dialect == "tsql":
            import re

            if re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
                return False, "T-SQL does not support LIMIT; use TOP instead"

        try:
            parsed = sqlglot.parse(sql.strip(), read=self.dialect)
        except sqlglot.errors.ParseError:
            return False, f"SQL failed to parse as {self.dialect}"
        except Exception:
            return False, f"Unable to parse SQL for dialect '{self.dialect}'"

        if not parsed:
            return False, f"Empty result after parsing as {self.dialect}"

        return True, None
