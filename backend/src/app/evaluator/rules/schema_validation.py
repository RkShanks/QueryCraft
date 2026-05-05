"""SchemaValidationRule — validates table/column references against schema."""

import sqlglot
from sqlglot import exp

from app.evaluator.schema_context import SchemaContext


class SchemaValidationRule:
    """Evaluator rule that checks SQL references only existing tables and columns."""

    name = "schema_validation"

    async def evaluate(self, sql: str, schema: SchemaContext | None) -> tuple[bool, str | None]:
        """Reject SQL referencing unknown tables or columns."""
        if schema is None or not schema.tables:
            return True, None

        try:
            parsed = sqlglot.parse(sql, read="postgres")
        except Exception:
            return False, "Unable to parse SQL"

        if not parsed or parsed[0] is None:
            return False, "Empty SQL"

        statement = parsed[0]

        # Build alias map: alias -> actual table name
        alias_map: dict[str, str] = {}
        for table in statement.find_all(exp.Table):
            alias_map[table.name] = table.name
            if table.alias:
                alias_map[table.alias] = table.name

        # Validate tables
        for table in statement.find_all(exp.Table):
            table_name = table.name
            is_quoted = hasattr(table.this, "quoted") and table.this.quoted
            found = self._find_table(schema, table_name, is_quoted)
            if not found:
                return False, f"Unknown table: {table_name}"

        # Validate columns
        for col in statement.find_all(exp.Column):
            col_name = col.name
            table_ref = col.table
            if not table_ref:
                # Unqualified column — check against all tables (allow if found anywhere)
                found = self._find_column_anywhere(schema, col_name)
                if not found:
                    return False, f"Unknown column: {col_name}"
                continue

            actual_table = alias_map.get(table_ref, table_ref)
            col_table_quoted = (
                hasattr(col.args.get("table"), "quoted") and col.args["table"].quoted
            )
            table_obj = self._find_table(schema, actual_table, col_table_quoted)
            if table_obj is None:
                return False, f"Unknown table for column: {actual_table}"

            found_col = self._find_column(table_obj, col_name)
            if not found_col:
                return False, f"Unknown column '{col_name}' in table '{actual_table}'"

        return True, None

    @staticmethod
    def _find_table(schema: SchemaContext, name: str, exact_case: bool = False):
        """Find a table by name, respecting case-sensitivity if quoted."""
        for table in schema.tables:
            if exact_case:
                if table.name == name:
                    return table
            else:
                if table.name.lower() == name.lower():
                    return table
        return None

    @staticmethod
    def _find_column_anywhere(schema: SchemaContext, name: str):
        """Find a column in any table."""
        for table in schema.tables:
            for col in table.columns:
                if col.name.lower() == name.lower():
                    return True
        return False

    @staticmethod
    def _find_column(table, name: str) -> bool:
        """Find a column in a specific table."""
        return any(col.name.lower() == name.lower() for col in table.columns)
