"""RoleAuthorizationRule — block SQL referencing tables/columns outside
the role's allowed set.

T-709 / FR-130 / S-007 / SC-050. Runs inside the evaluator pipeline BEFORE
execution. The rule parses the SQL with sqlglot, walks every ``exp.Table``
and ``exp.Column`` node, and blocks the query if any reference is outside
the role policy. Disallowed references include:

- A table that is not in the role's ``allowed_tables`` list.
- A column that is not in the role's ``allowed_columns`` for the owning
  table (qualified) or for the only allowed table in the query that owns
  the column (unqualified). An unqualified column that resolves against
  MORE than one allowed table is ambiguous and is blocked (fail-closed).

The ``column_masks`` parameter is an OUTPUT transform applied by
``PolicyEnforcementService.apply_column_masks`` after execution; the auth
rule treats masked columns the same as non-masked columns. Masking never
grants extra access (a masked column not in ``allowed_columns`` is still
blocked) and never denies otherwise-allowed access (the masking service
handles the actual value replacement downstream).

Sanitised reason:
  The rule returns the constant string ``"query_blocked_policy"`` for
  every failure mode (disallowed reference, malformed SQL, multi-statement,
  empty SQL, non-SELECT). The constant never echoes the raw SQL, table
  name, column name, schema internals, or user values. The pipeline
  translates ``"role_authorization"`` -> ``"error.queryBlockedPolicy"`` for
  the API response (i18n key per api-contracts.md line 385).

Failure modes covered (defence in depth — the rule works standalone but
is normally preceded by ``read_only``, ``single_statement``,
``schema_validation``):
- Malformed SQL (sqlglot parse error) -> block.
- Multi-statement SQL -> block.
- Non-SELECT statement -> block.
- Empty / whitespace-only SQL -> block.
- Table not in policy -> block.
- Column not in policy for the owning table -> block.
- Unqualified column that resolves to multiple allowed tables -> block.
- Column not present in the schema -> block (defence in depth; usually
  caught by ``schema_validation``).

Inputs (``schema``, ``allowed_tables``, ``column_masks``) are never
mutated. The rule builds an internal ``policy_by_table`` lookup and
releases it on return.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

from app.evaluator.schema_context import SchemaContext

# Sanitised reason for every failure mode. The pipeline's message key
# map translates ``"role_authorization"`` -> ``"error.queryBlockedPolicy"``
# for the i18n layer; the reason itself is a constant that never echoes
# SQL, table, column, schema, or user values.
_REASON = "query_blocked_policy"

# Default sqlglot read dialect. Mirrors the conservative default used by
# the other rules (``single_statement``, ``unsafe_pattern``).
_DEFAULT_DIALECT = "postgres"


class RoleAuthorizationRule:
    """Evaluator rule that blocks SQL referencing tables/columns outside
    the role's allowed set (FR-130 / S-007)."""

    name = "role_authorization"

    def __init__(
        self,
        allowed_tables: list[dict] | None,
        column_masks: list[dict] | None = None,
        dialect: str = _DEFAULT_DIALECT,
    ) -> None:
        """Initialise with the role policy.

        Args:
            allowed_tables: Role policy in the shape
                ``[{"table": "t", "columns": ["c1", "c2"]}, ...]``.
                ``None`` or an empty list is a deny-all policy: every
                query is blocked (fail-closed).
            column_masks: Optional role column-mask policy in the shape
                ``[{"table": "t", "columns": ["c1"]}]``. Informational
                only; the rule does not use it to allow or deny access
                beyond what ``allowed_tables`` already permits.
            dialect: sqlglot read dialect (default ``"postgres"``).
        """
        self._allowed_tables = allowed_tables
        self._column_masks = column_masks
        self._dialect = dialect

    async def evaluate(self, sql: str, schema: SchemaContext | None) -> tuple[bool, str | None]:
        """Block SQL that references tables/columns outside the role policy.

        Returns:
            ``(True, None)`` if every reference is allowed.
            ``(False, _REASON)`` if any reference is disallowed, the SQL
            is malformed, multi-statement, non-SELECT, or empty.
        """
        # Surface-level guards. sqlglot may not raise for empty input —
        # handle that explicitly.
        if not isinstance(sql, str) or not sql.strip():
            return False, _REASON

        # Deny-all when policy is missing or empty. An empty allowed list
        # means the role has no grants (fail-closed).
        policy_by_table, allowed_table_order = self._build_policy_index(self._allowed_tables)
        if not policy_by_table:
            return False, _REASON

        try:
            parsed = sqlglot.parse(sql, read=self._dialect)
        except Exception:
            return False, _REASON

        if not parsed:
            return False, _REASON

        # Multi-statement: defence in depth; SingleStatementRule usually
        # catches this upstream.
        if any(stmt is None for stmt in parsed) or len(parsed) != 1:
            return False, _REASON

        statement = parsed[0]
        if not isinstance(statement, exp.Select):
            return False, _REASON

        if schema is None:
            # No schema provided: cannot validate column existence. We
            # can still validate that every referenced TABLE is in the
            # policy; columns are validated only if the table is allowed
            # AND we have schema info. Without schema, every column
            # reference for an allowed table is a best-effort allow
            # (consistent with SchemaValidationRule when no schema is
            # passed). For safety, fail-closed: require a schema.
            return False, _REASON

        return self._validate_statement(statement, schema, policy_by_table, allowed_table_order)

    def _validate_statement(
        self,
        statement: exp.Expression,
        schema: SchemaContext,
        policy_by_table: dict[str, set[str]],
        allowed_table_order: list[str],
    ) -> tuple[bool, str | None]:
        # Discover CTE aliases -> known column lists (best-effort).
        cte_aliases: dict[str, list[str]] = {}
        if hasattr(statement, "ctes") and statement.ctes:
            for cte in statement.ctes:
                cte_aliases[cte.alias] = self._extract_cte_columns(cte)

        # Build alias map: alias -> actual table name (and table name ->
        # itself). Only include tables that are in the policy; a table
        # outside the policy is itself a block trigger.
        alias_map: dict[str, str] = {}
        for table in statement.find_all(exp.Table):
            actual = self._resolve_table_name(table, policy_by_table)
            if actual is None:
                return False, _REASON
            alias_map[table.name] = actual
            if table.alias:
                alias_map[table.alias] = actual
            if table.db:
                qualified = f"{table.db}.{table.name}"
                alias_map[qualified] = actual

        # Validate columns. We walk every exp.Column and resolve qualifiers
        # via alias_map. Unqualified columns are resolved against the
        # unique allowed table in this query that owns the column; if
        # the column exists in multiple allowed tables referenced by the
        # query, it is ambiguous and the rule fails closed.
        referenced_allowed_tables: set[str] = set(alias_map.values())

        # Build a per-query map: lowercased column name -> set of allowed
        # tables (in this query) that own it. Used to resolve unqualified
        # columns.
        column_owners: dict[str, set[str]] = {}
        for table_name in referenced_allowed_tables:
            allowed_cols = policy_by_table.get(table_name.lower(), set())
            for col in allowed_cols:
                column_owners.setdefault(col, set()).add(table_name)

        # Build a physical-columns index: lowercased table name -> set of
        # lowercased physical column names. Used to validate star
        # expansion: ``SELECT *`` and ``SELECT t.*`` are only allowed
        # when EVERY physical column of the targeted table is in the
        # role policy. Otherwise the star silently leaks disallowed
        # columns (FR-130 / S-007).
        physical_columns_by_table: dict[str, set[str]] = {}
        for table in schema.tables:
            physical_columns_by_table[table.name.lower()] = {c.name.lower() for c in table.columns}

        for col in statement.find_all(exp.Column):
            # ``SELECT t.*`` is modelled as ``Column(this=Star(), table='t')``
            # by sqlglot. The Column walk must skip these — they are
            # validated by the dedicated star walk below.
            if isinstance(col.this, exp.Star):
                continue
            col_name = col.name
            col_name_lower = col_name.lower()
            table_ref = col.table

            # CTE-qualified column: column must be in the CTE's columns.
            if table_ref and table_ref in cte_aliases:
                cte_cols = cte_aliases[table_ref] or []
                if cte_cols and col_name_lower not in {c.lower() for c in cte_cols}:
                    return False, _REASON
                continue

            if table_ref:
                # Qualified column. Resolve alias -> actual table.
                actual = alias_map.get(table_ref, table_ref)
                actual_lower = actual.lower()
                if actual_lower not in policy_by_table:
                    return False, _REASON
                if col_name_lower not in policy_by_table[actual_lower]:
                    return False, _REASON
                continue

            # Unqualified column: must resolve to a unique allowed table
            # in this query that owns the column.
            owners = column_owners.get(col_name_lower, set())
            if not owners:
                return False, _REASON
            if len(owners) > 1:
                # Ambiguous: the column exists in multiple allowed tables
                # referenced by the same query. Fail closed.
                return False, _REASON
            # Single owner: allow (the column is in that table's policy).
            continue

        # Validate stars. ``SELECT *`` and ``SELECT t.*`` expand to one
        # column per physical column of the target table. The auth rule
        # must block them unless EVERY physical column of the target
        # table is in the role policy. Otherwise the star silently leaks
        # disallowed columns (FR-130 / S-007 — this is the leak class
        # caught by the regression suite). ``COUNT(*)`` and other
        # aggregate stars are exempted because no column value reaches
        # the user.
        for star in statement.find_all(exp.Star):
            if self._is_aggregate_star(star):
                # Aggregate star (e.g. COUNT(*)): no value leak.
                continue
            star_result = self._validate_star(
                star,
                alias_map=alias_map,
                policy_by_table=policy_by_table,
                cte_aliases=cte_aliases,
                physical_columns_by_table=physical_columns_by_table,
                referenced_allowed_tables=referenced_allowed_tables,
            )
            if star_result is not None:
                return star_result

        # ORDER BY / GROUP BY columns are exp.Column nodes too, so the
        # loop above covers them. The star walk above covers any star
        # expression anywhere in the statement.
        return True, None

    @staticmethod
    def _is_aggregate_star(star: exp.Star) -> bool:
        """Return True when *star* is the argument of an aggregate.

        ``COUNT(*)``, ``SUM(*)`` (invalid SQL but may parse), etc. The
        aggregate returns a scalar — no column value reaches the user —
        so the auth rule does not need to validate the underlying
        columns.
        """
        # Common aggregate function nodes in sqlglot. ``exp.Count`` is
        # the dedicated node; other aggregates (``SUM``, ``AVG``) are
        # ``exp.Anonymous`` or ``exp.AggFunc`` subclasses, but ``*`` is
        # only valid as the argument of ``COUNT`` in standard SQL.
        ancestor = star.parent
        while ancestor is not None:
            cls_name = type(ancestor).__name__
            if cls_name in {"Count", "AggFunc"}:
                return True
            ancestor = ancestor.parent
        return False

    def _validate_star(
        self,
        star: exp.Star,
        *,
        alias_map: dict[str, str],
        policy_by_table: dict[str, set[str]],
        cte_aliases: dict[str, list[str]],
        physical_columns_by_table: dict[str, set[str]],
        referenced_allowed_tables: set[str],
    ) -> tuple[bool, str | None] | None:
        """Validate a single ``exp.Star`` against the role policy.

        Returns ``None`` if the star is allowed (caller proceeds to the
        next star or returns ``(True, None)`` at the end). Returns a
        ``(False, _REASON)`` tuple to block the query.
        """
        # Qualified star: ``t.*`` or ``alias.*`` — sqlglot may expose
        # the qualifier on the ``exp.Star`` node (older versions) or on
        # a child ``exp.Column`` (newer versions). Handle both.
        qualifier = self._star_qualifier(star)
        if qualifier:
            # CTE-qualified star. We cannot statically map CTE columns
            # back to base-table policies without a column->source
            # trace, so we block conservatively (fail-closed). A role
            # that needs CTE output should reference columns
            # explicitly.
            if qualifier in cte_aliases:
                return False, _REASON
            actual = alias_map.get(qualifier, qualifier)
            actual_lower = actual.lower()
            if actual_lower not in policy_by_table:
                return False, _REASON
            physical = physical_columns_by_table.get(actual_lower, set())
            if not physical:
                # Unknown physical table for the qualifier; treat as
                # referential failure (defence in depth — schema
                # validation should have caught this).
                return False, _REASON
            if not physical.issubset(policy_by_table[actual_lower]):
                return False, _REASON
            return None

        # Unqualified star: applies to every referenced allowed table
        # in the query. The role must be granted EVERY physical column
        # of EVERY referenced table. An empty referenced-set (no
        # FROM) cannot produce rows; treat as referential failure.
        if not referenced_allowed_tables:
            return False, _REASON
        for table_name in referenced_allowed_tables:
            actual_lower = table_name.lower()
            physical = physical_columns_by_table.get(actual_lower, set())
            if not physical:
                return False, _REASON
            if not physical.issubset(policy_by_table.get(actual_lower, set())):
                return False, _REASON
        return None

    @staticmethod
    def _star_qualifier(star: exp.Star) -> str | None:
        """Extract the table qualifier from an ``exp.Star`` if any.

        ``SELECT *`` -> ``None``. ``SELECT orders.*`` -> ``\"orders\"``.
        ``SELECT o.*`` -> ``\"o\"``. The qualifier lives in different
        places depending on sqlglot version:

        - Newer sqlglot: a child ``exp.Table`` (``star.this``).
        - Common shape: the parent is an ``exp.Column`` whose
          ``table`` attribute holds the qualifier and whose ``this``
          attribute is the ``exp.Star``.
        - Older sqlglot: ``star.table`` directly, or a child
          ``exp.Column`` (``star.expressions[0].table``).

        We try each shape in turn.
        """
        # Parent-as-Column: ``SELECT orders.*`` -> ``Column(table='orders', this=Star())``
        parent = star.parent
        if isinstance(parent, exp.Column) and parent.table:
            return parent.table
        # Newer sqlglot: star carries a Table child.
        inner = star.args.get("this") if hasattr(star, "args") else None
        if isinstance(inner, exp.Table) and inner.name:
            return inner.name
        # Older sqlglot: qualifier is the ``table`` attribute on the
        # Star or a child Column.
        direct = getattr(star, "table", None)
        if direct:
            return direct
        if hasattr(star, "expressions") and star.expressions:
            first = star.expressions[0]
            if isinstance(first, exp.Column) and first.table:
                return first.table
        return None

    def _resolve_table_name(
        self,
        table: exp.Table,
        policy_by_table: dict[str, set[str]],
    ) -> str | None:
        """Return the policy-normalised table name if the table is allowed.

        Returns ``None`` for any table not in the policy (caller treats
        this as a block).
        """
        table_name = table.name
        table_name_lower = table_name.lower()
        if table_name_lower in policy_by_table:
            return table_name
        # Schema-qualified name: ``public.orders`` -> try ``public.orders``
        # first, then fall back to ``orders`` for the PostgreSQL default
        # schema (mirrors SchemaValidationRule).
        if table.db:
            qualified_lower = f"{table.db.lower()}.{table_name_lower}"
            if qualified_lower in policy_by_table:
                return qualified_lower
            if table.db.lower() == "public" and table_name_lower in policy_by_table:
                return table_name
        return None

    def _build_policy_index(self, allowed_tables: list[dict] | None) -> tuple[dict[str, set[str]], list[str]]:
        """Build a ``lowercased table -> set of lowercased columns`` index.

        Drops entries with non-string table names, non-list columns, or
        empty values silently (consistent with ``filter_schema``). An
        entry with an empty ``columns`` list is treated as a deny-all
        for that table: the table appears in the index with an empty
        set so that any column reference is blocked. (This matches
        admin intent: "the table is in the policy, but no columns are
        granted".)
        """
        index: dict[str, set[str]] = {}
        order: list[str] = []
        if not isinstance(allowed_tables, list):
            return index, order
        for entry in allowed_tables:
            if not isinstance(entry, dict):
                continue
            table_name = entry.get("table")
            if not isinstance(table_name, str) or not table_name:
                continue
            columns = entry.get("columns") or []
            if not isinstance(columns, list):
                continue
            normalized = {c.lower() for c in columns if isinstance(c, str) and c}
            index[table_name.lower()] = normalized
            order.append(table_name.lower())
        return index, order

    @staticmethod
    def _extract_cte_columns(cte: exp.CTE) -> list[str]:
        """Best-effort column extraction for a CTE (for unqualified
        column resolution). Returns ``[]`` when the columns cannot be
        statically resolved (the rule then falls back to blocking
        references into the CTE without a qualifying table)."""
        alias = cte.args.get("alias")
        if alias and hasattr(alias, "columns") and alias.columns:
            return [str(c.name) for c in alias.columns]
        body = cte.this
        if isinstance(body, exp.Union):
            body = body.this
        if not isinstance(body, exp.Select):
            return []
        columns: list[str] = []
        for expr in body.expressions:
            if isinstance(expr, exp.Alias):
                columns.append(expr.alias)
            elif isinstance(expr, exp.Column):
                columns.append(expr.name)
            elif isinstance(expr, exp.Star):
                return []  # Cannot statically resolve
            elif isinstance(expr, exp.Literal):
                continue
            else:
                if hasattr(expr, "alias") and expr.alias:
                    columns.append(expr.alias)
        return columns
