"""Tests for T-703: row filter injection at query time.

Covers FR-131 / SC-051. ``apply_row_filters()`` takes a generated SQL
statement and a list of role-configured row filters, parses the
generated SQL with sqlglot, AND-conjunctions each filter into the
WHERE clause (or adds a WHERE if none exists), binds ``{user.*}``
placeholders to driver-appropriate parameters, and transpiles back to
the target dialect.

The function does NOT receive the generated SQL's own bind values;
those are the caller's responsibility (T-711/T-712 query flow). The
``params`` returned by this function contain only row-filter values.

Schema-drift behavior is covered separately in
``test_schema_drift_guard.py`` (T-705). These tests use schemas that
match the filter columns.
"""

from __future__ import annotations

import pytest
import sqlglot
from sqlglot.optimizer.scope import traverse_scope

from app.evaluator.schema_context import Column, SchemaContext, Table
from app.services.policy_enforcement import (
    BoundSql,
    PolicyEnforcementService,
)

USER = {"email": "a@b.c", "subject_id": "sso|x", "role": "analyst"}


def _schema() -> SchemaContext:
    """Single ``orders`` table with id / region / note / owner columns."""
    return SchemaContext(
        tables=[
            Table(
                name="orders",
                schema_name="public",
                columns=[
                    Column(name="id", type="integer", nullable=False, primary_key=True),
                    Column(name="region", type="text", nullable=False),
                    Column(name="note", type="text", nullable=True),
                    Column(name="owner_email", type="text", nullable=True),
                ],
            ),
        ]
    )


def _schema_with_customer() -> SchemaContext:
    return SchemaContext(
        tables=[
            *_schema().tables,
            Table(
                name="customer",
                schema_name="public",
                columns=[
                    Column(name="customer_id", type="integer"),
                    Column(name="owner_email", type="text"),
                ],
            ),
        ]
    )


# ──────────────────────── Adding WHERE when missing ────────────────────────


class TestNoExistingWhereGetsWhere:
    def test_filter_added_as_where_postgres(self) -> None:
        sql = "SELECT id, region FROM orders"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert "WHERE" in result.sql
        assert "region = $1" in result.sql
        assert result.params == ("analyst",)

    def test_filter_added_as_where_mysql(self) -> None:
        sql = "SELECT id FROM orders"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="mysql",
        )
        assert "WHERE" in result.sql
        assert "%s" in result.sql
        assert result.params == ("analyst",)

    def test_filter_added_as_where_mssql(self) -> None:
        sql = "SELECT id FROM orders"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="mssql",
        )
        assert "WHERE" in result.sql
        assert "?" in result.sql
        assert result.params == ("analyst",)

    def test_filter_added_for_tsql_api_dialect(self) -> None:
        """The query API routes MSSQL connections through ``tsql``."""
        sql = "SELECT TOP 10 id FROM orders"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="tsql",
        )
        assert "TOP 10" in result.sql
        assert "region = ?" in result.sql
        assert result.params == ("analyst",)


# ──────────────────────── AND-conjunction when WHERE exists ────────────────────────


class TestExistingWhereGetsAnd:
    def test_appends_and_postgres(self) -> None:
        sql = "SELECT id FROM orders WHERE id > 10"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert "WHERE id > 10" in result.sql
        assert "AND" in result.sql
        assert "region = $1" in result.sql
        assert result.params == ("analyst",)

    def test_appends_and_mysql(self) -> None:
        sql = "SELECT id FROM orders WHERE id = 10"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="mysql",
        )
        assert "WHERE id = 10" in result.sql
        assert "AND" in result.sql
        assert "%s" in result.sql
        assert result.params == ("analyst",)

    def test_appends_and_mssql(self) -> None:
        sql = "SELECT id FROM orders WHERE id = 10"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="mssql",
        )
        assert "WHERE id = 10" in result.sql
        assert "AND" in result.sql
        assert "?" in result.sql
        assert result.params == ("analyst",)


# ──────────────────────── Physical-table scope ────────────────────────


class TestPhysicalTableScope:
    def test_join_filter_is_qualified_to_target_alias(self) -> None:
        schema = SchemaContext(
            tables=[
                *_schema().tables,
                Table(
                    name="payments",
                    columns=[
                        Column(name="order_id", type="integer"),
                        Column(name="region", type="text"),
                    ],
                ),
            ]
        )

        result = PolicyEnforcementService.apply_row_filters(
            sql=("SELECT o.id, p.order_id FROM orders AS o JOIN payments AS p ON p.order_id = o.id"),
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=schema,
            user_context=USER,
            dialect="postgres",
        )

        assert "o.region = $1" in result.sql
        assert result.params == ("analyst",)

    def test_cte_filter_is_injected_into_physical_source_scope(self) -> None:
        result = PolicyEnforcementService.apply_row_filters(
            sql=("WITH scoped_orders AS (SELECT id, region FROM orders) SELECT id FROM scoped_orders"),
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )

        scopes = traverse_scope(sqlglot.parse_one(result.sql, read="postgres"))
        assert scopes[0].expression.args.get("where") is not None
        assert scopes[1].expression.args.get("where") is None
        assert result.params == ("analyst",)

    def test_cte_filter_params_follow_rendered_scope_order(self) -> None:
        result = PolicyEnforcementService.apply_row_filters(
            sql=(
                "WITH scoped_orders AS (SELECT id, region FROM orders), "
                "scoped_customers AS (SELECT customer_id, owner_email FROM customer) "
                "SELECT scoped_orders.id FROM scoped_orders "
                "JOIN scoped_customers ON scoped_customers.customer_id = scoped_orders.id"
            ),
            row_filters=[
                {"table": "customer", "filter": "owner_email = {user.email}"},
                {"table": "orders", "filter": "region = {user.role}"},
            ],
            schema=_schema_with_customer(),
            user_context=USER,
            dialect="postgres",
        )

        assert "region = $1" in result.sql
        assert "owner_email = $2" in result.sql
        assert result.params == ("analyst", "a@b.c")

    def test_tsql_schema_qualified_filter_matches_exact_physical_table(self) -> None:
        schema = SchemaContext(
            tables=[
                Table(
                    name="Customer",
                    schema_name="SalesLT",
                    columns=[
                        Column(name="CustomerID", type="integer"),
                        Column(name="OwnerEmail", type="text"),
                    ],
                )
            ]
        )

        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT c.CustomerID FROM SalesLT.Customer AS c",
            row_filters=[
                {
                    "table": "SalesLT.Customer",
                    "filter": "OwnerEmail = {user.email}",
                }
            ],
            schema=schema,
            user_context=USER,
            dialect="tsql",
        )

        assert "c.OwnerEmail = ?" in result.sql
        assert result.params == ("a@b.c",)

    def test_tsql_filter_resolves_flattened_introspection_table_name(self) -> None:
        schema = SchemaContext(
            tables=[
                Table(
                    name="SalesLT.Customer",
                    columns=[
                        Column(name="CustomerID", type="integer"),
                        Column(name="OwnerEmail", type="text"),
                    ],
                )
            ]
        )

        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT c.CustomerID FROM SalesLT.Customer AS c",
            row_filters=[
                {
                    "table": "SalesLT.Customer",
                    "filter": "OwnerEmail = {user.email}",
                }
            ],
            schema=schema,
            user_context=USER,
            dialect="tsql",
        )

        assert "c.OwnerEmail = ?" in result.sql
        assert result.params == ("a@b.c",)

    @pytest.mark.parametrize(
        ("dialect", "placeholder"),
        [
            pytest.param("postgres", "$1", id="postgres"),
            pytest.param("mysql", "%s", id="mysql"),
            pytest.param("tsql", "?", id="tsql"),
        ],
    )
    def test_self_join_filters_every_physical_alias(
        self,
        dialect: str,
        placeholder: str,
    ) -> None:
        result = PolicyEnforcementService.apply_row_filters(
            sql=(
                "SELECT first_order.id FROM orders AS first_order "
                "JOIN orders AS second_order ON second_order.id = first_order.id"
            ),
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect=dialect,
        )

        assert f"first_order.region = {placeholder}" in result.sql
        second_placeholder = "$2" if dialect == "postgres" else placeholder
        assert f"second_order.region = {second_placeholder}" in result.sql
        assert result.params == ("analyst", "analyst")

    @pytest.mark.parametrize(
        ("dialect", "sql"),
        [
            pytest.param("postgres", "SELECT COUNT(*) FROM orders", id="aggregate"),
            pytest.param(
                "postgres",
                "SELECT nested.id FROM (SELECT id FROM orders) AS nested",
                id="nested",
            ),
            pytest.param(
                "mysql",
                "WITH scoped AS (SELECT id FROM orders) SELECT id FROM scoped",
                id="cte",
            ),
            pytest.param(
                "mysql",
                "SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS rn FROM orders",
                id="window",
            ),
            pytest.param(
                "tsql",
                "SELECT TOP 5 id FROM orders ORDER BY id",
                id="pagination",
            ),
        ],
    )
    def test_unrelated_filter_preserves_valid_read_shapes(
        self,
        dialect: str,
        sql: str,
    ) -> None:
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[
                {
                    "table": "customer",
                    "filter": "owner_email = {user.email}",
                }
            ],
            schema=_schema_with_customer(),
            user_context=USER,
            dialect=dialect,
        )

        assert "owner_email" not in result.sql.lower()
        assert result.params == ()

    def test_nested_filter_is_injected_only_into_physical_source(self) -> None:
        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT nested.id FROM (SELECT id, region FROM orders) AS nested",
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )

        scopes = traverse_scope(sqlglot.parse_one(result.sql, read="postgres"))
        assert scopes[0].expression.args.get("where") is not None
        assert scopes[1].expression.args.get("where") is None
        assert result.params == ("analyst",)

    def test_qualified_policy_does_not_match_same_table_in_other_schema(self) -> None:
        schema = SchemaContext(
            tables=[
                Table(
                    name="Customer",
                    schema_name=schema_name,
                    columns=[Column(name="OwnerEmail", type="text")],
                )
                for schema_name in ("SalesLT", "Archive")
            ]
        )

        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT OwnerEmail FROM Archive.Customer",
            row_filters=[
                {
                    "table": "SalesLT.Customer",
                    "filter": "OwnerEmail = {user.email}",
                }
            ],
            schema=schema,
            user_context=USER,
            dialect="tsql",
        )

        assert "WHERE" not in result.sql
        assert result.params == ()


# ──────────────────────── Postgres start_index after existing params ────────────────────────


class TestPostgresStartIndex:
    def test_three_existing_params_starts_at_four(self) -> None:
        """Generated SQL uses ``$1, $2, $3``; new filter must be ``$4``."""
        sql = "SELECT id FROM orders WHERE a = $1 AND b = $2 AND c = $3"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert "region = $4" in result.sql
        assert "$1" in result.sql
        assert "$2" in result.sql
        assert "$3" in result.sql
        assert result.params == ("analyst",)

    def test_existing_with_gap_starts_above_max(self) -> None:
        """Even with gaps (``$1`` and ``$5``), our new placeholder is ``$6``,
        not ``$3`` (count + 1). Take max + 1 to avoid collisions.
        """
        sql = "SELECT id FROM orders WHERE a = $1 AND b = $5"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert "region = $6" in result.sql
        assert result.params == ("analyst",)


# ──────────────────────── Multiple filters on same table ────────────────────────


class TestMultipleFilters:
    def test_multiple_filters_and_together_postgres(self) -> None:
        sql = "SELECT id FROM orders"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[
                {"table": "orders", "filter": "region = {user.role}"},
                {"table": "orders", "filter": "owner_email = {user.email}"},
            ],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert "region = $1" in result.sql
        assert "owner_email = $2" in result.sql
        assert " AND " in result.sql
        assert result.params == ("analyst", "a@b.c")

    def test_multiple_filters_and_together_mysql(self) -> None:
        sql = "SELECT id FROM orders"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[
                {"table": "orders", "filter": "region = {user.role}"},
                {"table": "orders", "filter": "owner_email = {user.email}"},
            ],
            schema=_schema(),
            user_context=USER,
            dialect="mysql",
        )
        assert "region = %s" in result.sql
        assert "owner_email = %s" in result.sql
        assert " AND " in result.sql
        assert result.params == ("analyst", "a@b.c")

    def test_three_filters(self) -> None:
        sql = "SELECT id FROM orders"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[
                {"table": "orders", "filter": "region = {user.role}"},
                {"table": "orders", "filter": "owner_email = {user.email}"},
                {"table": "orders", "filter": "id > 0"},
            ],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert "region = $1" in result.sql
        assert "owner_email = $2" in result.sql
        # Third filter is a literal (no placeholder), so the literal ``0``
        # appears verbatim — no $3 placeholder emitted.
        assert "id > 0" in result.sql
        assert result.params == ("analyst", "a@b.c")

    def test_empty_filter_list_returns_unmodified_sql(self) -> None:
        sql = "SELECT id FROM orders WHERE id = 1"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert "WHERE id = 1" in result.sql
        assert "AND" not in result.sql
        assert result.params == ()


# ──────────────────────── Dialect transpilation smoke ────────────────────────


class TestDialectTranspilation:
    def test_mysql_output_uses_percent_s(self) -> None:
        sql = "SELECT id FROM orders"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="mysql",
        )
        assert "$" not in result.sql
        assert "%s" in result.sql

    def test_mssql_output_uses_question_mark(self) -> None:
        sql = "SELECT id FROM orders"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="mssql",
        )
        assert "$" not in result.sql
        assert "?" in result.sql
        assert "%s" not in result.sql

    def test_postgres_output_uses_dollar_n(self) -> None:
        sql = "SELECT id FROM orders"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert "$1" in result.sql
        assert "?" not in result.sql
        assert "%s" not in result.sql


# ──────────────────────── Malformed / unsupported SQL rejected ────────────────────────


class TestMalformedInput:
    def test_unparseable_generated_sql_rejected(self) -> None:
        """Garbage input SQL must not crash — the operation fails closed."""
        with pytest.raises(ValueError, match="filter_injection_failed"):
            PolicyEnforcementService.apply_row_filters(
                sql="NOT VALID SQL @@@",
                row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                schema=_schema(),
                user_context=USER,
                dialect="postgres",
            )

    def test_non_select_generated_sql_rejected(self) -> None:
        """Generated SQL must be a SELECT (DML/DDL already blocked by
        evaluator; this is a defense-in-depth check at injection time).
        """
        with pytest.raises(ValueError, match="filter_injection_failed"):
            PolicyEnforcementService.apply_row_filters(
                sql="DROP TABLE orders",
                row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                schema=_schema(),
                user_context=USER,
                dialect="postgres",
            )

    def test_multi_statement_generated_sql_rejected(self) -> None:
        with pytest.raises(ValueError, match="filter_injection_failed"):
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT 1; SELECT 2",
                row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                schema=_schema(),
                user_context=USER,
                dialect="postgres",
            )


# ──────────────────────── BoundSql shape ────────────────────────


class TestReturnsBoundSql:
    def test_returns_bound_sql_instance(self) -> None:
        sql = "SELECT id FROM orders"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert isinstance(result, BoundSql)

    def test_params_is_tuple(self) -> None:
        sql = "SELECT id FROM orders"
        result = PolicyEnforcementService.apply_row_filters(
            sql=sql,
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert isinstance(result.params, tuple)

    def test_input_schema_not_mutated(self) -> None:
        """The caller passes a SchemaContext; the service must not mutate it."""
        schema = _schema()
        before_tables = [(t.name, tuple(c.name for c in t.columns)) for t in schema.tables]
        PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders",
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=schema,
            user_context=USER,
            dialect="postgres",
        )
        after_tables = [(t.name, tuple(c.name for c in t.columns)) for t in schema.tables]
        assert before_tables == after_tables

    def test_user_value_never_appears_in_sql(self) -> None:
        ctx = {"email": "evil'; DROP TABLE x;--", "subject_id": "x", "role": "analyst"}
        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders",
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=ctx,
            dialect="postgres",
        )
        assert "evil" not in result.sql
        assert "DROP" not in result.sql
        assert "--" not in result.sql
        assert result.params == ("analyst",)


# ──────────────────────── PR #126 blockers: string-literal preservation ────────────────────────
# These guard against raw-string replacement that previously mutated
# characters inside SQL string literals. The driver-style rendering and
# the internal ``?`` normalization must both skip single-quoted and
# double-quoted content. See PR #126 for the original bug reports.


class TestStringLiteralPreservation:
    def test_postgres_generated_sql_literal_question_preserved(self) -> None:
        """Bug 1 (PR #126): ``WHERE note = '?'`` must stay verbatim;
        only the row-filter placeholder may be renumbered to ``$N``.
        The literal ``?`` does NOT consume a placeholder slot.
        """
        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders WHERE note = '?'",
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert "'?'" in result.sql
        assert "'$1'" not in result.sql
        assert "region = $1" in result.sql
        assert result.params == ("analyst",)

    def test_mysql_generated_sql_literal_question_preserved(self) -> None:
        """Bug 2 mirror (PR #126): MySQL output must not turn a literal
        ``'?'`` into ``'%s'``. The literal stays; only the row-filter
        placeholder becomes ``%s``.
        """
        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders WHERE note = '?'",
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="mysql",
        )
        assert "'?'" in result.sql
        assert "'%s'" not in result.sql
        assert "region = %s" in result.sql
        assert result.params == ("analyst",)

    def test_mssql_generated_sql_literal_question_preserved(self) -> None:
        """MSSQL is positional; existing ``?`` placeholders coexist
        with the new one. A literal ``'?'`` must not collide.
        """
        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders WHERE note = '?'",
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="mssql",
        )
        assert "'?'" in result.sql
        assert "region = ?" in result.sql
        assert result.params == ("analyst",)

    def test_mysql_filter_literal_percent_s_preserved(self) -> None:
        """Bug 2 (PR #126): a literal ``%s`` in the filter fragment
        (inside a string) must NOT be re-rendered to ``?`` during the
        internal normalization step, and must still appear as ``%s``
        in the output (because the literal never changed).
        """
        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders",
            row_filters=[
                {"table": "orders", "filter": "region = 'a%s' OR region = {user.role}"},
            ],
            schema=_schema(),
            user_context=USER,
            dialect="mysql",
        )
        assert "'a%s'" in result.sql
        # The actual row-filter placeholder is a single ``%s`` (not four).
        # Count the ``%s`` outside the literal: there should be exactly
        # one for the {user.role} bind value.
        import re

        outside = re.sub(r"'[^']*(?:''[^']*)*'", "", result.sql)
        assert outside.count("%s") == 1
        assert result.params == ("analyst",)

    def test_postgres_filter_literal_question_preserved(self) -> None:
        """A literal ``?`` in the filter fragment (postgres dialect,
        inside a string) must NOT be re-rendered to ``$N`` during the
        final renumbering pass. The row-filter ``{user.role}`` becomes
        ``$N``; the literal ``?`` stays as ``?``.
        """
        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders",
            row_filters=[
                {"table": "orders", "filter": "note = '?' OR region = {user.role}"},
            ],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert "'?'" in result.sql
        assert "region = $1" in result.sql
        # The literal ``?`` is still a literal ``?`` — it was NOT turned
        # into ``$1`` by the renumbering pass.
        import re

        outside = re.sub(r"'[^']*(?:''[^']*)*'", "", result.sql)
        assert outside.count("$1") == 1
        assert result.params == ("analyst",)

    def test_escaped_single_quote_in_string_literal_handled(self) -> None:
        """SQL escapes a single quote inside a string by doubling:
        ``'don''t'``. The lexer must treat the whole span as one
        literal — the inner ``'`` does not close the string.
        """
        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders WHERE note = 'don''t?'",
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )
        # The whole string literal is preserved verbatim, including the
        # trailing ``?``.
        assert "'don''t?'" in result.sql
        assert "region = $1" in result.sql

    def test_double_quoted_identifier_with_question_preserved_postgres(self) -> None:
        """Quoted identifiers (``"my col"``) containing a ``?`` must
        also be skipped by the renumbering pass.
        """
        result = PolicyEnforcementService.apply_row_filters(
            sql='SELECT id FROM orders AS "my?"',
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert '"my?"' in result.sql
        assert "region = $1" in result.sql

    def test_string_literal_with_dollar_n_preserved_postgres(self) -> None:
        """A literal that already contains ``$1`` (e.g. user data
        that looks like a placeholder) must not be touched.
        """
        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders WHERE note = '$1 shouldn''t collide'",
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert "'$1 shouldn''t collide'" in result.sql
        # The literal ``$1`` does not consume a placeholder slot.
        assert "region = $1" in result.sql


# ──────────────────────── PR #126 blocker: MySQL backtick identifiers ────────────────────────
# ``validate_row_filter`` accepts MySQL backtick-quoted identifiers
# (e.g. ``\`region\```) at save time. ``apply_row_filters`` must also
# accept them at injection time. The previous hard-coded ``read="tsql"``
# re-parse rejected backticks, raising ``filter_injection_failed``.


class TestMySQLBacktickIdentifier:
    def test_backtick_column_in_filter_injects_for_mysql(self) -> None:
        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders",
            row_filters=[{"table": "orders", "filter": "`region` = {user.role}"}],
            schema=_schema(),
            user_context=USER,
            dialect="mysql",
        )
        # Backticks are preserved verbatim; only the placeholder style
        # is converted to mysql's ``%s``.
        assert "`region` = %s" in result.sql
        assert result.params == ("analyst",)

    def test_backtick_filter_validates_at_save_time(self) -> None:
        """Sanity check: backtick identifier also passes validation
        (the save-time path), so injection must match.
        """
        PolicyEnforcementService.validate_row_filter("`region` = {user.role}", _schema(), "orders", dialect="mysql")
