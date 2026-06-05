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
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import sqlglot
from sqlglot import exp

from app.evaluator.schema_context import Column, SchemaContext, Table

# Constant error code for any binding failure. Intentionally opaque to avoid
# leaking which key was missing or what dialect was requested.
_PLACEHOLDER_BINDING_FAILED = "placeholder_binding_failed"

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
        """Resolve ``{user.*}`` placeholders to dialect parameter tokens + values.

        The input ``filter_sql`` is the already-validated fragment from
        ``validate_row_filter``. Each ``{user.<key>}`` occurrence is
        replaced in left-to-right order with a dialect-appropriate
        placeholder (``$N`` for postgres, ``%s`` for mysql, ``?`` for
        mssql) and the corresponding value is appended to ``params`` in
        the same order. User values are never interpolated into the SQL
        string — they live only in ``params``.

        Args:
            filter_sql: Validated filter fragment containing zero or more
                ``{user.email}`` / ``{user.subject_id}`` / ``{user.role}``
                occurrences.
            user_context: Mapping with the resolved user values. Each
                ``{user.<key>}`` placeholder looks up ``<key>`` in this
                dict; missing or ``None`` values fail closed.
            dialect: Target sqlglot driver dialect. Unknown dialects
                fail closed.
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

        # ``re.sub`` with a function repl is safe — match positions are
        # scanned left-to-right, replacement is verbatim.
        try:
            new_sql = _PLACEHOLDER_RE.sub(_replace, filter_sql)
        except ValueError:
            # Already a binding failure; re-raise unchanged.
            raise

        # Reject any leftover ``{user.`` shapes that the regex did not
        # match (e.g. ``{user.}`` or ``{user.XY}`` with weird chars). The
        # validator should have caught these at save time, but binding is
        # the second line of defense.
        if re.search(r"\{user\.", new_sql):
            raise ValueError(_PLACEHOLDER_BINDING_FAILED)

        return BoundSql(sql=new_sql, params=tuple(params))


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
