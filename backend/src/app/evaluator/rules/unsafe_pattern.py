"""UnsafePatternRule — rejects platform-defined unsafe SQL patterns."""

import sqlglot
from sqlglot import exp

from app.evaluator.schema_context import SchemaContext

# Forbidden function names (case-insensitive)
_FORBIDDEN_FUNCTIONS = {
    "pg_sleep",
    "lo_export",
    "lo_import",
    "lo_read",
    "lo_write",
    "lo_create",
    "lo_unlink",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_logdir_ls",
    "pg_read_file_all",
    "pg_stat_file",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "pg_reload_conf",
    "dblink",
    "dblink_connect",
    "dblink_disconnect",
    "dblink_exec",
    "dblink_get_result",
    "dblink_get_connections",
    "dblink_is_busy",
    "dblink_send_query",
    "pg_advisory_lock",
    "pg_advisory_unlock",
    "pg_advisory_lock_shared",
    "pg_advisory_xact_lock",
    "pg_try_advisory_lock",
    "pg_try_advisory_xact_lock",
    "set_config",
    "current_setting",
    "pg_promote",
    "pg_switch_wal",
    "pg_backup_start",
    "pg_backup_stop",
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

    def __init__(self):
        self._forbidden_functions = set(_FORBIDDEN_FUNCTIONS)

    def add_pattern(self, pattern: str) -> None:
        """Add a forbidden function name at runtime (FR-010f extensibility)."""
        self._forbidden_functions.add(pattern.lower())

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

        # Reject LISTEN / NOTIFY / UNLISTEN and raw SET commands
        if isinstance(statement, exp.Command):
            cmd = (statement.this or "").strip().upper()
            if cmd == "SET":
                return False, "SET statement is not allowed"

        # sqlglot parses LISTEN / NOTIFY / UNLISTEN as Alias(Column(...), ...)
        if isinstance(statement, exp.Alias):
            inner = statement.this
            if isinstance(inner, exp.Column):
                inner_name = inner.name.upper()
                if inner_name in {"LISTEN", "NOTIFY", "UNLISTEN"}:
                    return False, f"{inner_name} statement is not allowed"

        # Check for forbidden functions (handles both plain str and quoted Identifier)
        for func in statement.find_all(exp.Anonymous):
            func_name = getattr(func, "this", None)
            name = None
            if isinstance(func_name, str):
                name = func_name
            elif isinstance(func_name, exp.Identifier):
                name = func_name.this
            if name and name.lower() in self._forbidden_functions:
                return False, f"Forbidden function: {name}"

        # Check for forbidden system tables
        for table in statement.find_all(exp.Table):
            table_name = table.name.lower()
            if table_name in _FORBIDDEN_TABLES:
                return False, f"Forbidden system table: {table_name}"

        return True, None
