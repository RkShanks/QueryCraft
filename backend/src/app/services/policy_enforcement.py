"""PolicyEnforcementService — central policy enforcement for query pipeline.

T-699: Schema filtering. Applies RoleConnectionPolicy.allowed_tables to a
SchemaContext, returning a new SchemaContext that contains only role-permitted
tables and columns. Used to restrict the LLM prompt to role-permitted schema
per S-006 / FR-128 / FR-129 / SC-050.

T-701: Row filter validation. Parses an admin-authored WHERE fragment at save
time, rejecting dangerous expressions and validating column existence against
the target table per S-004 / FR-131. Placeholder syntax (``{user.email}``,
``{user.subject_id}``, ``{user.role}``) is allowed syntactically but not bound
here; T-702/T-704 cover binding and injection.

T-702: Placeholder binding. Translates ``{user.*}`` placeholders inside an
already-validated filter fragment into dialect-appropriate parameterized
placeholders (``$N`` for postgres, ``%s`` for mysql, ``?`` for mssql) plus a
params tuple. FR-131 / S-004.

T-704: Row filter injection. Injects per-role row filters into a generated
SQL statement via sqlglot AST AND-conjunction, transpiling the result to the
target dialect, with schema-drift detection. FR-131 / S-005.

T-705: Schema drift guard. Re-checks every column reference in every
row filter against the current connection schema at injection time. A
missing column or table raises ``PolicySchemaConflictError`` and emits
``AuditActionType.POLICY_SCHEMA_MISMATCH`` via the optional ``audit_hook``.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import sqlglot
from sqlglot import exp

from app.core.exceptions import PolicySchemaConflictError
from app.db.models.enums import AuditActionType
from app.evaluator.schema_context import Column, SchemaContext, Table

# Type alias for the optional audit hook passed to ``apply_row_filters``.
# The hook receives the action type and a sanitized payload (table name
# only — never the filter SQL, column name, or user values).
AuditHook = Callable[[AuditActionType, dict[str, Any]], None]

# Constant error code for any binding failure. Intentionally opaque to avoid
# leaking which key was missing or what dialect was requested.
_PLACEHOLDER_BINDING_FAILED = "placeholder_binding_failed"

# Constant error code for any injection failure. Intentionally opaque:
# does not leak the offending SQL, schema, or dialect.
_FILTER_INJECTION_FAILED = "filter_injection_failed"

# Placeholder token per dialect driver:
# - asyncpg (postgres): ``$1``, ``$2``, ... (numbered, configurable start)
# - asyncmy (mysql):    ``%s`` (positional)
# - aioodbc (mssql):    ``?`` (positional)
_DIALECT_PARAM_STYLE: dict[str, str] = {
    "postgres": "numbered",
    "postgresql": "numbered",
    "mysql": "positional",
    "mssql": "positional",
}

# Map our public dialect name to the sqlglot dialect name used for parsing
# and transpilation. ``tsql`` is the sqlglot name for Microsoft SQL Server.
_SQLGLOT_DIALECT: dict[str, str] = {
    "postgres": "postgres",
    "postgresql": "postgres",
    "mysql": "mysql",
    "mssql": "tsql",
}

# Allowed identity placeholders. Anything else inside ``{...}`` is rejected.
_ALLOWED_PLACEHOLDER_KEYS: frozenset[str] = frozenset({"email", "subject_id", "role"})

# User-context keys the binding step looks up. Mirrors the placeholder keys.
_USER_CONTEXT_KEYS: dict[str, str] = {
    "email": "email",
    "subject_id": "subject_id",
    "role": "role",
}

# Sentinel prefix used to swap placeholders for parseable identifiers before
# sqlglot sees the fragment. The column-existence check skips any column whose
# name starts with this prefix.
_PH_SENTINEL_PREFIX = "__ph_user_"

_PLACEHOLDER_RE = re.compile(r"\{user\.([a-zA-Z0-9_]+)\}")

# AST node classes that signal a non-SELECT, write, or set-operation statement.
# Any of these appearing under the wrapper means the fragment is not a legal
# row filter.
_DANGEROUS_TOPLEVEL: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
    exp.Copy,
    exp.Set,
)

# Boolean/arithmetic/comparison operator class names that sqlglot models as
# ``exp.Func`` subclasses. In a WHERE clause these are NOT function calls and
# must be excluded from the function-call rejection step. Real function calls
# (LOWER, COALESCE, AVG, current_user, foo(), etc.) are caught by name.
_NON_FUNCTION_OPS: frozenset[str] = frozenset(
    {
        # Logical
        "And",
        "Or",
        "Not",
        "Xor",
        "Paren",
        # Comparison
        "EQ",
        "NEQ",
        "GT",
        "GTE",
        "LT",
        "LTE",
        "Is",
        "In",
        "Between",
        "Like",
        "ILike",
        "SimilarTo",
        "RegexpLike",
        # Arithmetic / string concat
        "Add",
        "Sub",
        "Mul",
        "Div",
        "Mod",
        "Concat",
        "DPipe",
        "Pipe",
        # Null tests
        "IsNull",
        "NotNull",
        # Boolean literal
        "Boolean",
        # Negation / distinct
        "Neg",
        "Distinct",
    }
)


def _contains_comment_outside_string(sql: str) -> bool:
    """Return True if ``--`` or ``/*`` appears outside a string literal."""
    i = 0
    n = len(sql)
    in_single = False
    in_double = False
    while i < n:
        c = sql[i]
        if c == "'" and not in_double:
            if i + 1 < n and sql[i + 1] == "'":
                i += 2
                continue
            in_single = not in_single
            i += 1
            continue
        if c == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue
        if in_single or in_double:
            i += 1
            continue
        if c == "-" and i + 1 < n and sql[i + 1] == "-":
            return True
        if c == "/" and i + 1 < n and sql[i + 1] == "*":
            return True
        i += 1
    return False


class PolicyEnforcementService:
    """Stateless service that applies role policy to evaluator schema inputs.

    The service is intentionally a plain class with no constructor arguments
    so it can be instantiated freely and called from any query pipeline stage.
    """

    @staticmethod
    def filter_schema(
        schema: SchemaContext,
        allowed_tables: list[dict] | None,
    ) -> SchemaContext:
        """Return a new SchemaContext containing only role-allowed tables/columns.

        Args:
            schema: The full SchemaContext (e.g., from connection introspection).
            allowed_tables: Role policy in the shape
                ``[{"table": "t", "columns": ["c1", "c2"]}, ...]``. ``None`` or
                an empty list is treated as a deny-all policy (fail-closed).

        Returns:
            A new ``SchemaContext``. The input is never mutated. Tables and
            columns not present in the policy are silently excluded.
            ``schema_name`` and column metadata are preserved verbatim.
        """
        if not allowed_tables:
            return SchemaContext(tables=[])

        # Index policy by lowercased table name for case-insensitive lookup.
        # Unknown policy entries (tables/columns not in schema) are dropped
        # silently — no leak, no exception.
        policy_by_table: dict[str, set[str]] = {}
        for entry in allowed_tables:
            table_name = entry.get("table")
            if not isinstance(table_name, str) or not table_name:
                continue
            columns = entry.get("columns") or []
            if not isinstance(columns, list):
                continue
            normalized_cols = {c.lower() for c in columns if isinstance(c, str)}
            policy_by_table[table_name.lower()] = normalized_cols

        filtered_tables: list[Table] = []
        for table in schema.tables:
            allowed_cols = policy_by_table.get(table.name.lower())
            if allowed_cols is None:
                continue

            kept_columns: list[Column] = [column for column in table.columns if column.name.lower() in allowed_cols]
            filtered_tables.append(
                Table(
                    name=table.name,
                    schema_name=table.schema_name,
                    columns=kept_columns,
                )
            )

        return SchemaContext(tables=filtered_tables)

    @staticmethod
    def validate_row_filter(
        filter_sql: str,
        schema: SchemaContext,
        table_name: str,
        dialect: str = "postgres",
    ) -> None:
        """Validate an admin-authored row filter fragment at save time.

        Wraps the fragment as ``SELECT 1 WHERE <filter>`` and parses with
        sqlglot to reject dangerous expressions and validate column existence
        against the target table (S-004, FR-131).

        The fragment may contain identity placeholders (``{user.email}``,
        ``{user.subject_id}``, ``{user.role}``); these are accepted
        syntactically and replaced with sentinel identifiers for parsing.
        Placeholder binding and injection safety are T-702/T-704.

        Args:
            filter_sql: Admin-authored WHERE fragment for a single table.
            schema: Connection schema (must contain ``table_name``).
            table_name: Target table the filter applies to.
            dialect: sqlglot read dialect (default ``"postgres"``).

        Raises:
            ValueError: ``"filter_validation_failed"`` for any validation
                failure. The message is intentionally constant so it cannot
                leak the fragment, schema names, or driver internals.
        """
        # 1. Surface-level shape checks (fail fast before parsing).
        if not isinstance(filter_sql, str):
            raise ValueError("filter_validation_failed")
        if not filter_sql.strip():
            raise ValueError("filter_validation_failed")

        # 2. Comments are rejected up-front. sqlglot strips comments by
        #    default, so the AST alone cannot detect them.
        if _contains_comment_outside_string(filter_sql):
            raise ValueError("filter_validation_failed")

        # 3. Target table must exist in the schema (fail-closed).
        target_table = schema.find_table(table_name)
        if target_table is None:
            raise ValueError("filter_validation_failed")
        valid_columns: set[str] = {c.name.lower() for c in target_table.columns}

        # 4. Replace known placeholders with sentinel identifiers; reject
        #    anything else that looks like a placeholder. Unknown placeholders
        #    raise immediately so the admin gets a clear "not allowed" signal
        #    rather than a confusing parse error.
        def _replace_placeholder(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in _ALLOWED_PLACEHOLDER_KEYS:
                raise ValueError("filter_validation_failed")
            return f"{_PH_SENTINEL_PREFIX}{key}__"

        processed_sql = _PLACEHOLDER_RE.sub(_replace_placeholder, filter_sql)

        # 5. Parse the fragment wrapped as a single SELECT. Reject parse
        #    errors, empty input, or multiple statements outright.
        wrapped = f"SELECT 1 WHERE {processed_sql}"
        try:
            parsed = sqlglot.parse(wrapped, read=dialect)
        except Exception:
            # Suppress the chained sqlglot exception — it could leak fragment
            # or driver internals. Callers see only the opaque code.
            raise ValueError("filter_validation_failed") from None

        if not parsed or len(parsed) != 1 or parsed[0] is None:
            raise ValueError("filter_validation_failed")

        statement = parsed[0]
        if not isinstance(statement, exp.Select):
            raise ValueError("filter_validation_failed")

        # 6. Reject dangerous top-level nodes (DML/DDL/COPY/SET/Command).
        for node_type in _DANGEROUS_TOPLEVEL:
            if statement.find(node_type):
                raise ValueError("filter_validation_failed")

        # 7. Reject set operations (UNION/INTERSECT/EXCEPT) anywhere in the
        #    tree. The wrapper is a single SELECT, so any set op means the
        #    fragment itself contained one (e.g. "a=1 UNION SELECT ...").
        if statement.find(exp.Union) or statement.find(exp.Intersect) or statement.find(exp.Except):
            raise ValueError("filter_validation_failed")

        # 8. Reject any nested SELECT (subqueries). The wrapper itself is a
        #    Select, so we skip it. CTEs are not subqueries for this purpose.
        outer = statement
        for sub in outer.find_all(exp.Select):
            if sub is outer:
                continue
            if any(cte.this is sub for cte in outer.find_all(exp.CTE)):
                continue
            raise ValueError("filter_validation_failed")

        # 9. Reject any function call. exp.Func is the base class for every
        #    function-like node in sqlglot, including exp.Anonymous (unknown
        #    function calls) and special nodes like exp.CurrentUser. Boolean
        #    operators, comparisons, and arithmetic are also modeled as
        #    exp.Func in sqlglot — those are excluded by name.
        for func in statement.find_all(exp.Func):
            if type(func).__name__ in _NON_FUNCTION_OPS:
                continue
            raise ValueError("filter_validation_failed")

        # 10. Validate every Column reference. The target table owns the
        #     columns; placeholder sentinels (and only sentinels) are skipped.
        #     If a qualifier is present, it must match the target table
        #     case-insensitively. Without this check, ``customers.id`` would
        #     leak across to a target table that also has an ``id`` column
        #     (PR #125 blocker).
        target_table_lower = target_table.name.lower()
        for col in statement.find_all(exp.Column):
            col_name = col.name
            if col_name.startswith(_PH_SENTINEL_PREFIX):
                continue
            if col.table and col.table.lower() != target_table_lower:
                raise ValueError("filter_validation_failed")
            if col_name.lower() in valid_columns:
                continue
            raise ValueError("filter_validation_failed")

    @staticmethod
    def bind_placeholders(
        filter_sql: str,
        user_context: dict[str, Any],
        dialect: str = "postgres",
        start_index: int = 1,
    ) -> BoundSql:
        """Resolve ``{user.*}`` placeholders to driver parameter tokens + values.

        The input ``filter_sql`` is the already-validated fragment from
        ``validate_row_filter``. Each ``{user.<key>}`` occurrence is
        replaced in left-to-right order with a driver-appropriate
        placeholder (``$N`` for postgres, ``%s`` for mysql, ``?`` for
        mssql) and the corresponding value is appended to ``params`` in
        the same order. User values are never interpolated into the SQL
        string — they live only in ``params``.

        This is the public binding entry point used by
        ``apply_row_filters`` and any other caller. The function does
        NOT use sqlglot to parse the fragment — the input is a simple
        string with ``{user.*}`` placeholders and the output is a
        string with driver-style placeholders.

        Args:
            filter_sql: Validated filter fragment containing zero or more
                ``{user.email}`` / ``{user.subject_id}`` / ``{user.role}``
                occurrences.
            user_context: Mapping with the resolved user values. Each
                ``{user.<key>}`` placeholder looks up ``<key>`` in this
                dict; missing or ``None`` values fail closed.
            dialect: Target driver dialect. Unknown dialects fail
                closed.
            start_index: For numbered dialects, the index of the first
                emitted parameter (default ``1``). Ignored for
                positional dialects.

        Returns:
            ``BoundSql(sql, params)``. ``params`` is a tuple of values in
            the same order as the placeholder occurrences in the SQL.

        Raises:
            ValueError: ``"placeholder_binding_failed"`` for unknown
                placeholder, missing/``None`` user value, unknown
                dialect, or non-string ``filter_sql``.
        """
        if not isinstance(filter_sql, str):
            raise ValueError(_PLACEHOLDER_BINDING_FAILED)
        if not isinstance(user_context, dict):
            raise ValueError(_PLACEHOLDER_BINDING_FAILED)
        if dialect.lower() not in _DIALECT_PARAM_STYLE:
            raise ValueError(_PLACEHOLDER_BINDING_FAILED)

        params: list[Any] = []
        occurrence = 0

        def _replace(match: re.Match[str]) -> str:
            nonlocal occurrence
            key = match.group(1)
            if key not in _ALLOWED_PLACEHOLDER_KEYS:
                raise ValueError(_PLACEHOLDER_BINDING_FAILED)
            ctx_key = _USER_CONTEXT_KEYS[key]
            if ctx_key not in user_context:
                raise ValueError(_PLACEHOLDER_BINDING_FAILED)
            value = user_context[ctx_key]
            if value is None:
                raise ValueError(_PLACEHOLDER_BINDING_FAILED)
            params.append(value)
            token = _placeholder_token(dialect, start_index, occurrence)
            occurrence += 1
            return token

        try:
            new_sql = _PLACEHOLDER_RE.sub(_replace, filter_sql)
        except ValueError:
            raise

        # Reject any leftover ``{user.`` shapes that the regex did not
        # match (e.g. ``{user.}`` or ``{user.XY}`` with weird chars). The
        # validator should have caught these at save time, but binding is
        # the second line of defense.
        if re.search(r"\{user\.", new_sql):
            raise ValueError(_PLACEHOLDER_BINDING_FAILED)

        return BoundSql(sql=new_sql, params=tuple(params))

    @staticmethod
    def apply_row_filters(
        sql: str,
        row_filters: list[dict[str, Any]],
        schema: SchemaContext,
        user_context: dict[str, Any],
        dialect: str = "postgres",
        audit_hook: AuditHook | None = None,
    ) -> BoundSql:
        """Inject per-role row filters into a generated SQL statement.

        Each ``row_filters`` entry is ``{"table": str, "filter": str}``.
        The ``filter`` is a WHERE-condition fragment already validated
        by ``validate_row_filter`` and may contain ``{user.*}``
        placeholders.

        The generated ``sql`` is parsed with sqlglot in the target
        dialect. For each filter:
        1. Schema drift is checked — every column in the bound filter
           must exist in the current ``schema`` for the filter's
           table. A missing column or table raises
           ``PolicySchemaConflictError`` (T-705). The optional
           ``audit_hook`` receives
           ``(POLICY_SCHEMA_MISMATCH, {"table": ...})`` first.
        2. Placeholders are bound to driver-appropriate tokens via
           ``bind_placeholders`` (postgres: ``$N`` continuing from
           max+1 of the existing SQL; mysql: ``%s``; mssql: ``?``).
        3. The bound filter is normalized to use ``?`` placeholders
           internally and re-parsed as ``SELECT 1 WHERE <bound>``.
        4. Its WHERE expression is AND-conjunctions into the main
           statement's WHERE (or added as a new WHERE if none exists).
        5. Bound values are appended to the returned ``params`` tuple.

        After AST manipulation, the final SQL is renumbered to the
        target driver's style:
        - postgres / asyncpg: ``$N`` starting at ``max+1``
        - mysql / asyncmy: ``%s`` (positional)
        - mssql / aioodbc: ``?`` (positional, native)

        Args:
            sql: Generated SQL statement, already transpiled to the
                target dialect.
            row_filters: Role-configured row filters. Each must have
                string ``table`` and string ``filter`` keys.
            schema: Current connection schema. Used for drift checks
                on every column reference in every filter.
            user_context: Mapping with resolved user values for
                placeholder binding.
            dialect: Target driver dialect (one of ``postgres``,
                ``mysql``, ``mssql``).
            audit_hook: Optional callable invoked with
                ``(AuditActionType, payload)`` when a drift is
                detected. The payload contains the admin-configured
                ``table`` name only — never the filter SQL, the
                missing column, or user values.

        Returns:
            ``BoundSql`` with the rewritten SQL in the target driver's
            placeholder style and the row-filter parameter values (in
            occurrence order). User values are never interpolated.

        Raises:
            PolicySchemaConflictError: A filter references a column or
                table removed from the current schema (schema drift).
                The error is sanitized: no SQL, column, or user-value
                leak. Constant message and i18n message key
                ``error.policySchemaConflict``.
            ValueError: ``"filter_injection_failed"`` for malformed
                input, unparseable SQL, non-SELECT generated SQL,
                multi-statement input, or any bind failure.
        """
        if not isinstance(sql, str):
            raise ValueError(_FILTER_INJECTION_FAILED)
        if not isinstance(row_filters, list):
            raise ValueError(_FILTER_INJECTION_FAILED)
        if not isinstance(schema, SchemaContext):
            raise ValueError(_FILTER_INJECTION_FAILED)
        if not isinstance(user_context, dict):
            raise ValueError(_FILTER_INJECTION_FAILED)

        sqlglot_dialect = _SQLGLOT_DIALECT.get(dialect.lower())
        if sqlglot_dialect is None:
            raise ValueError(_FILTER_INJECTION_FAILED)

        # Parse the generated SQL. Reject parse errors, multi-statement
        # input, and non-SELECT statements.
        try:
            parsed = sqlglot.parse(sql, read=sqlglot_dialect)
        except Exception:
            raise ValueError(_FILTER_INJECTION_FAILED) from None
        if not parsed or len(parsed) != 1 or parsed[0] is None:
            raise ValueError(_FILTER_INJECTION_FAILED)
        stmt = parsed[0]
        if not isinstance(stmt, exp.Select):
            raise ValueError(_FILTER_INJECTION_FAILED)

        # Compute the postgres start_index from existing $N placeholders.
        # For mysql/mssql, ignored by the renumbering pass.
        start_index = _next_postgres_index(stmt, sqlglot_dialect)
        render_start_index = start_index  # captured before any advancement

        params: list[Any] = []
        for rf in row_filters:
            if not isinstance(rf, dict):
                raise ValueError(_FILTER_INJECTION_FAILED)
            table_name = rf.get("table")
            filter_sql = rf.get("filter")
            if not isinstance(table_name, str) or not isinstance(filter_sql, str):
                raise ValueError(_FILTER_INJECTION_FAILED)

            # Bind placeholders to the driver's native style. The
            # internal AST re-uses ``?`` (Placeholder) regardless of
            # driver, so the driver-specific token from bind_placeholders
            # is converted back to ``?`` for parsing here. The
            # post-processing step at the end re-emits driver style.
            bound = PolicyEnforcementService.bind_placeholders(filter_sql, user_context, dialect, start_index)
            params.extend(bound.params)
            internal_filter_sql = _to_internal_placeholder(bound.sql, dialect)

            # T-705: schema drift guard. Parse the bound filter and
            # check every column reference still exists in the
            # current schema. Drift raises PolicySchemaConflictError
            # (sanitized) and emits the audit hook with a payload
            # containing only the table name.
            _check_schema_drift(
                internal_filter_sql,
                table_name,
                schema,
                sqlglot_dialect,
                audit_hook,
            )

            # Parse the bound filter wrapped as a SELECT so we can lift
            # its WHERE expression for AND-conjunction. Parse in tsql
            # (which understands ``?``) regardless of target dialect
            # to keep the internal format uniform.
            wrapped = f"SELECT 1 WHERE {internal_filter_sql}"
            try:
                filter_stmt = sqlglot.parse_one(wrapped, read="tsql")
            except Exception:
                raise ValueError(_FILTER_INJECTION_FAILED) from None
            if not isinstance(filter_stmt, exp.Select):
                raise ValueError(_FILTER_INJECTION_FAILED)
            filter_where = filter_stmt.args.get("where")
            if filter_where is None:
                raise ValueError(_FILTER_INJECTION_FAILED)
            new_expr = filter_where.this

            # AND-conjunction (or add new WHERE).
            existing = stmt.args.get("where")
            if existing is None:
                stmt = stmt.where(new_expr)
            else:
                stmt.set("where", exp.Where(this=exp.and_(existing.this, new_expr)))

            # Advance the start_index for the next filter.
            start_index += len(bound.params)

        # Serialize back to the target sqlglot dialect, then convert
        # the ``?`` placeholders (added by us) to driver style.
        out_sql = stmt.sql(dialect=sqlglot_dialect)
        out_sql = _render_placeholders_for_driver(out_sql, dialect.lower(), render_start_index)
        return BoundSql(sql=out_sql, params=tuple(params))


def _next_postgres_index(stmt: exp.Expression, sqlglot_dialect: str) -> int:
    """Return the next safe ``$N`` index for a postgres SELECT.

    For postgres we take ``max($N) + 1`` to avoid colliding with any
    existing placeholder, even if there are gaps. For mysql/mssql the
    parameter style is positional so we start at 1 (ignored).
    """
    if sqlglot_dialect != "postgres":
        return 1
    max_index = 0
    for param in stmt.find_all(exp.Parameter):
        node = param.this
        if isinstance(node, exp.Literal) and node.is_string is False:
            try:
                idx = int(node.this)
            except (TypeError, ValueError):
                continue
            if idx > max_index:
                max_index = idx
    return max_index + 1


def _to_internal_placeholder(filter_sql: str, dialect: str) -> str:
    """Convert driver-style placeholders to internal ``?`` for AST merging.

    Maps ``$1`` → ``?`` (postgres) and ``%s`` → ``?`` (mysql). MSSQL
    already uses ``?`` so the input is returned unchanged. This is the
    inverse of ``_render_placeholders_for_driver``.
    """
    if dialect in ("mysql",):
        return filter_sql.replace("%s", "?")
    if dialect in ("postgres", "postgresql"):
        return re.sub(r"\$\d+", "?", filter_sql)
    return filter_sql  # mssql or unknown — leave as is


def _render_placeholders_for_driver(sql_str: str, dialect: str, start_index: int) -> str:
    """Convert internal ``?`` placeholders to the target driver's style.

    - postgres: ``?`` → ``$N`` numbered from ``start_index`` (left-to-right)
    - mysql:    ``?`` → ``%s``
    - mssql:    ``?`` is native, no change

    The renumbering pass for postgres replaces every ``?`` in
    left-to-right order. Existing ``$N`` tokens (from the generated
    SQL) are preserved verbatim.
    """
    if dialect in ("mssql",):
        return sql_str
    if dialect in ("mysql",):
        return sql_str.replace("?", "%s")
    if dialect in ("postgres", "postgresql"):
        counter = [start_index]

        def _sub(match: re.Match[str]) -> str:
            token = f"${counter[0]}"
            counter[0] += 1
            return token

        return re.sub(r"\?", _sub, sql_str)
    return sql_str


def _check_schema_drift(
    internal_filter_sql: str,
    table_name: str,
    schema: SchemaContext,
    sqlglot_dialect: str,
    audit_hook: AuditHook | None,
) -> None:
    """Verify every column in the bound filter still exists in the schema.

    T-705. Drift means a column (or the whole table) was removed from
    the connection schema between the time the filter was saved and
    the time the query is being injected. Drift raises
    ``PolicySchemaConflictError`` (sanitized constant message +
    ``error.policySchemaConflict`` i18n key) and, if provided,
    invokes the audit hook with ``POLICY_SCHEMA_MISMATCH`` and a
    payload containing only the table name (no filter SQL, no column
    name, no user values).

    The check is case-insensitive on column/table names to match
    Postgres identifier folding.
    """
    table = schema.find_table(table_name)
    if table is None:
        _emit_drift(audit_hook, table_name)
        raise PolicySchemaConflictError()
    valid_columns = {c.name.lower() for c in table.columns}

    wrapped = f"SELECT 1 WHERE {internal_filter_sql}"
    try:
        stmt = sqlglot.parse_one(wrapped, read=sqlglot_dialect)
    except Exception:
        # If the bound filter is unparseable, we cannot guarantee the
        # column set. Treat as drift — fail-closed.
        _emit_drift(audit_hook, table_name)
        raise PolicySchemaConflictError() from None

    if not isinstance(stmt, exp.Select):
        _emit_drift(audit_hook, table_name)
        raise PolicySchemaConflictError()

    for col in stmt.find_all(exp.Column):
        # Placeholder sentinels (T-702 internal) never appear here, but
        # guard anyway: any column whose name starts with the sentinel
        # prefix is a user-context substitution, not a real column.
        if col.name.startswith(_PH_SENTINEL_PREFIX):
            continue
        if col.name.lower() not in valid_columns:
            _emit_drift(audit_hook, table_name)
            raise PolicySchemaConflictError()


def _emit_drift(audit_hook: AuditHook | None, table_name: str) -> None:
    """Fire the audit hook for a drift event, if one was provided.

    The payload is sanitized: only the admin-configured table name
    leaks. No filter SQL, no missing column, no user values.
    """
    if audit_hook is None:
        return
    # Audit failure must not block the raise that follows. The caller
    # still sees PolicySchemaConflictError regardless.
    with contextlib.suppress(Exception):
        audit_hook(AuditActionType.POLICY_SCHEMA_MISMATCH, {"table": table_name})


@dataclass(frozen=True)
class BoundSql:
    """Parameterized SQL ready to hand to a source-DB adapter.

    Attributes:
        sql: SQL string with dialect-appropriate placeholders (``$N``,
            ``%s``, or ``?``). No user-supplied values are interpolated.
        params: Positional parameter values, one per placeholder occurrence.
    """

    sql: str
    params: tuple[Any, ...]


def _placeholder_token(dialect: str, start_index: int, occurrence: int) -> str:
    """Return the dialect-appropriate placeholder for a single occurrence.

    Postgres uses numbered ``$N`` starting at ``start_index``; MySQL and
    MSSQL use positional ``%s`` / ``?`` with ``start_index`` ignored.
    """
    style = _DIALECT_PARAM_STYLE.get(dialect.lower())
    if style is None:
        raise ValueError(_PLACEHOLDER_BINDING_FAILED)
    if style == "numbered":
        return f"${start_index + occurrence}"
    if style == "positional":
        return "%s" if dialect.lower() == "mysql" else "?"
    raise ValueError(_PLACEHOLDER_BINDING_FAILED)  # pragma: no cover
