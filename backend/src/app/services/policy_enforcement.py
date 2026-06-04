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
"""

from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

from app.evaluator.schema_context import Column, SchemaContext, Table

# Allowed identity placeholders. Anything else inside ``{...}`` is rejected.
_ALLOWED_PLACEHOLDER_KEYS: frozenset[str] = frozenset({"email", "subject_id", "role"})

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
        for col in statement.find_all(exp.Column):
            col_name = col.name
            if col_name.startswith(_PH_SENTINEL_PREFIX):
                continue
            if col_name.lower() in valid_columns:
                continue
            raise ValueError("filter_validation_failed")
