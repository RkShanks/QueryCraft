"""Schema context for evaluator rules.

Pydantic models representing the database schema against which SQL is validated.
"""

from pydantic import BaseModel


class Column(BaseModel):
    """Column metadata."""

    name: str
    type: str = "text"
    nullable: bool = True
    primary_key: bool = False


class Table(BaseModel):
    """Table metadata."""

    name: str
    schema_name: str = "public"
    columns: list[Column] = []


class SchemaContext(BaseModel):
    """Full schema context used by evaluator rules."""

    tables: list[Table] = []

    def find_table(self, name: str) -> Table | None:
        """Find a table by name, respecting Postgres identifier folding."""
        for table in self.tables:
            # Postgres folds unquoted identifiers to lowercase.
            if table.name.lower() == name.lower():
                return table
        return None

    def find_column(self, table_name: str, column_name: str) -> Column | None:
        """Find a column in a table."""
        table = self.find_table(table_name)
        if table is None:
            return None
        for column in table.columns:
            if column.name.lower() == column_name.lower():
                return column
        return None
