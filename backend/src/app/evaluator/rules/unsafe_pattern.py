"""UnsafePatternRule — rejects platform-defined unsafe SQL patterns."""

import sqlglot
from sqlglot import exp

from app.evaluator.schema_context import SchemaContext

# Forbidden function names (case-insensitive)
_FORBIDDEN_FUNCTIONS = {
    "pg_sleep",
    "lo_export",
    "lo_import",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_logdir_ls",
    "pg_read_file_all",
    "pg_stat_file",
}

# Forbidden table / schema names (system catalogs)
_FORBIDDEN_TABLES = {
    "pg_authid",
    "pg_shadow",
    "pg_user",
    "pg_roles",
    "pg_database",
    "pg_hba_file_rules",
    "pg_ident_file_mappings",
}


class UnsafePatternRule:
    """Evaluator rule that rejects known unsafe SQL patterns."""

    name = "unsafe_pattern"

    async def evaluate(self, sql: str, schema: SchemaContext | None) -> tuple[bool, str | None]:
        """Reject SQL containing forbidden functions, system tables, or statements."""
        try:
            parsed = sqlglot.parse(sql, read="postgres")
        except Exception:
            return False, "Unable to parse SQL"

        if not parsed or parsed[0] is None:
            return False, "Empty SQL"

        statement = parsed[0]

        # Reject COPY and SET statements outright
        if isinstance(statement, exp.Copy):
            return False, "COPY statement is not allowed"
        if isinstance(statement, exp.Set):
            return False, "SET statement is not allowed"

        # Check for forbidden functions
        for func in statement.find_all(exp.Anonymous):
            func_name = getattr(func, "this", None)
            if isinstance(func_name, str) and func_name.lower() in _FORBIDDEN_FUNCTIONS:
                return False, f"Forbidden function: {func_name}"

        # Check for forbidden system tables
        for table in statement.find_all(exp.Table):
            table_name = table.name.lower()
            if table_name in _FORBIDDEN_TABLES:
                return False, f"Forbidden system table: {table_name}"

        return True, None
