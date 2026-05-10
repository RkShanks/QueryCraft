"""SchemaValidationRule — validates table/column references against schema."""

import sqlglot
from sqlglot import exp

from app.evaluator.schema_context import SchemaContext


class SchemaValidationRule:
    """Evaluator rule that checks SQL references only existing tables and columns."""

    name = "schema_validation"

    def __init__(self, schema: SchemaContext | None = None):
        self._schema = schema

    async def evaluate(self, sql: str, schema: SchemaContext | None = None) -> tuple[bool, str | None]:
        """Reject SQL referencing unknown tables or columns."""
        effective_schema = schema or self._schema
        if effective_schema is None or not effective_schema.tables:
            return True, None

        try:
            parsed = sqlglot.parse(sql, read="postgres")
        except Exception:
            return False, "Unable to parse SQL"

        if not parsed or parsed[0] is None:
            return False, "Empty SQL"

        statement = parsed[0]
        return self._validate_statement(statement, effective_schema)

    def _validate_statement(
        self,
        statement: exp.Expression,
        schema: SchemaContext,
        cte_aliases: dict[str, list[str]] | None = None,
    ) -> tuple[bool, str | None]:
        """Validate a single statement against the schema and known CTE aliases."""
        cte_aliases = cte_aliases or {}

        # Recursively validate set operations (Union/Intersect/Except)
        if isinstance(statement, (exp.Union, exp.Intersect, exp.Except)):
            left = self._validate_statement(statement.this, schema, cte_aliases)
            if not left[0]:
                return left
            right = self._validate_statement(statement.expression, schema, cte_aliases)
            if not right[0]:
                return right
            return True, None

        # Discover CTEs defined in this statement and merge with inherited ones
        local_ctes: dict[str, list[str]] = dict(cte_aliases)
        if hasattr(statement, "ctes") and statement.ctes:
            for cte in statement.ctes:
                alias = cte.alias
                cols = self._extract_cte_columns(cte, schema)
                local_ctes[alias] = cols

            # Validate each CTE body recursively (with CTE aliases visible)
            for cte in statement.ctes:
                result = self._validate_statement(cte.this, schema, local_ctes)
                if not result[0]:
                    return result

        # Build alias map for real tables: alias -> actual table name
        alias_map: dict[str, str] = {}
        for table in statement.find_all(exp.Table):
            alias_map[table.name] = table.name
            if table.alias:
                alias_map[table.alias] = table.name

        # Validate tables
        for table in statement.find_all(exp.Table):
            table_name = table.name
            if table_name in local_ctes:
                continue
            # Reject cross-schema access (Phase 1 only supports default schema)
            if table.db:
                return False, f"Cross-schema access not allowed: {table.db}.{table_name}"
            is_quoted = hasattr(table.this, "quoted") and table.this.quoted
            found = self._find_table(schema, table_name, is_quoted)
            if not found:
                return False, f"Unknown table: {table_name}"

        # Validate columns
        for col in statement.find_all(exp.Column):
            col_name = col.name
            table_ref = col.table
            if not table_ref:
                # Unqualified column — check schema tables and CTE columns
                found = self._find_column_anywhere(schema, col_name)
                if not found:
                    found = any(
                        col_name.lower() == c.lower()
                        for cte_cols in local_ctes.values()
                        for c in cte_cols
                    )
                if not found:
                    return False, f"Unknown column: {col_name}"
                continue

            # Qualified column
            if table_ref in local_ctes:
                cte_cols = local_ctes[table_ref]
                # If we know CTE columns, validate; otherwise be lenient
                if cte_cols and col_name.lower() not in (c.lower() for c in cte_cols):
                    return False, f"Unknown column '{col_name}' in CTE '{table_ref}'"
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
    def _extract_cte_columns(cte: exp.CTE, schema: SchemaContext) -> list[str]:
        """Extract output column names from a CTE definition."""
        # Explicit column list: WITH cte(a, b) AS ...
        alias = cte.args.get("alias")
        if alias and hasattr(alias, "columns") and alias.columns:
            return [str(c.name) for c in alias.columns]

        body = cte.this
        # For Union, inspect the left side
        if isinstance(body, exp.Union):
            body = body.this

        if not isinstance(body, exp.Select):
            return []

        columns: list[str] = []
        has_star = False
        for expr in body.expressions:
            if isinstance(expr, exp.Alias):
                columns.append(expr.alias)
            elif isinstance(expr, exp.Column):
                columns.append(expr.name)
            elif isinstance(expr, exp.Star):
                has_star = True
            elif isinstance(expr, exp.Literal):
                # Literals without alias don't contribute named columns
                pass
            else:
                # For other expressions, try to get an alias if present
                if hasattr(expr, "alias") and expr.alias:
                    columns.append(expr.alias)

        if has_star:
            # Resolve SELECT * against tables in the CTE body
            from_tables = list(body.find_all(exp.Table))
            if len(from_tables) == 1:
                tname = from_tables[0].name
                table_obj = SchemaValidationRule._find_table(schema, tname, False)
                if table_obj:
                    star_cols = [c.name for c in table_obj.columns]
                    # Merge: star columns plus any explicitly named expressions
                    # that come after the star (typically star is first)
                    # We return all known columns from the table
                    return star_cols
        return columns

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
