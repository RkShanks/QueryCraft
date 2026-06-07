"""T-762/T-763/T-764 — Cross-dialect policy enforcement verification (Wave 17.5b).

Unit-level verification of the PolicyEnforcementService row filter and column
mask enforcement across PostgreSQL, MySQL, and MSSQL dialects.

These tests verify:
1. Row filters are applied fail-closed per dialect (postgres $N, mysql %s, mssql ?).
2. Column masks are dialect-agnostic (post-query result replacement).
3. Schema drift blocks query before execution regardless of dialect.
4. Filter injection produces correct AST conjunction per dialect.
5. No user context values leak into the generated SQL string.
6. Unauthorized tables/columns never enter filtered schema.

The integration-level evidence is T-721 (test_cross_dialect_policy.py) which
runs against real PG/MySQL/MSSQL. These unit tests verify the same contracts
without requiring live databases.

FR-131, FR-132, SC-051, SC-052.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import PolicySchemaConflictError
from app.evaluator.schema_context import Column, SchemaContext, Table
from app.schemas.query import ColumnMeta, QueryResult
from app.services.policy_enforcement import PolicyEnforcementService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DIALECTS = ["postgres", "mysql", "mssql"]

_USER = {"email": "test@example.com", "subject_id": "sso|user1", "role": "analyst"}


def _make_schema(table_name: str = "orders") -> SchemaContext:
    return SchemaContext(
        tables=[
            Table(
                name=table_name,
                schema_name="public",
                columns=[
                    Column(name="id", type="integer", nullable=False, primary_key=True),
                    Column(name="region", type="text", nullable=False),
                    Column(name="customer_email", type="text", nullable=True),
                    Column(name="ssn", type="text", nullable=True),
                    Column(name="amount", type="numeric", nullable=False),
                ],
            ),
            Table(
                name="secret_table",
                schema_name="public",
                columns=[
                    Column(name="id", type="integer", nullable=False, primary_key=True),
                    Column(name="internal_data", type="text", nullable=True),
                ],
            ),
        ]
    )


def _make_result(table_name: str = "orders") -> QueryResult:
    return QueryResult(
        attempt_id=str(uuid.uuid4()),
        session_id="test-session",
        question="How many orders by region?",
        generated_sql=f"SELECT id, region, ssn, amount FROM {table_name}",
        columns=[
            ColumnMeta(name="id", type="integer"),
            ColumnMeta(name="region", type="text"),
            ColumnMeta(name="ssn", type="text"),
            ColumnMeta(name="amount", type="numeric"),
        ],
        rows=[
            [1, "east", "111-11-1111", 100],
            [2, "east", "222-22-2222", 200],
            [3, "west", "333-33-3333", 300],
        ],
        row_count=3,
        attempt_number=1,
        is_last_auto_retry=False,
    )


# ---------------------------------------------------------------------------
# T-762/T-763/T-764: Row filter injection per dialect
# ---------------------------------------------------------------------------


class TestRowFilterInjectionPerDialect:
    """Verify row filter injection for all 3 supported dialects."""

    @pytest.mark.parametrize("dialect", _DIALECTS)
    def test_filter_injected_into_where_clause(self, dialect: str) -> None:
        """Row filter is AND-conjuncted into the WHERE clause."""
        schema = _make_schema()
        bound = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id, region FROM orders",
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=schema,
            user_context=_USER,
            dialect=dialect,
        )
        assert "WHERE" in bound.sql.upper()
        assert len(bound.params) == 1
        assert bound.params[0] == "analyst"

    @pytest.mark.parametrize("dialect", _DIALECTS)
    def test_no_raw_user_values_in_sql(self, dialect: str) -> None:
        """User context values are parameterized, never interpolated."""
        schema = _make_schema()
        bound = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders",
            row_filters=[{"table": "orders", "filter": "customer_email = {user.email}"}],
            schema=schema,
            user_context=_USER,
            dialect=dialect,
        )
        assert "test@example.com" not in bound.sql
        assert "{user" not in bound.sql
        assert bound.params == ("test@example.com",)

    @pytest.mark.parametrize("dialect", _DIALECTS)
    def test_multiple_filters_all_injected(self, dialect: str) -> None:
        """Multiple row filters are AND-conjuncted."""
        schema = _make_schema()
        bound = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders",
            row_filters=[
                {"table": "orders", "filter": "region = {user.role}"},
                {"table": "orders", "filter": "customer_email = {user.email}"},
            ],
            schema=schema,
            user_context=_USER,
            dialect=dialect,
        )
        assert len(bound.params) == 2
        assert bound.params[0] == "analyst"
        assert bound.params[1] == "test@example.com"

    def test_postgres_uses_dollar_placeholders(self) -> None:
        schema = _make_schema()
        bound = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders",
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=schema,
            user_context=_USER,
            dialect="postgres",
        )
        assert "$" in bound.sql
        assert "%s" not in bound.sql

    def test_mysql_uses_percent_s_placeholders(self) -> None:
        schema = _make_schema()
        bound = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders",
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=schema,
            user_context=_USER,
            dialect="mysql",
        )
        assert "%s" in bound.sql
        assert "$" not in bound.sql

    def test_mssql_uses_question_mark_placeholders(self) -> None:
        schema = _make_schema()
        bound = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders",
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=schema,
            user_context=_USER,
            dialect="mssql",
        )
        assert "?" in bound.sql
        assert "$" not in bound.sql
        assert "%s" not in bound.sql


# ---------------------------------------------------------------------------
# T-762/T-763/T-764: Schema drift guard per dialect
# ---------------------------------------------------------------------------


class TestSchemaDriftGuardPerDialect:
    """Row filters fail-closed when schema drifts, regardless of dialect."""

    @pytest.mark.parametrize("dialect", _DIALECTS)
    def test_drift_raises_before_execution(self, dialect: str) -> None:
        """Filter referencing a missing column raises PolicySchemaConflictError."""
        schema = SchemaContext(
            tables=[
                Table(
                    name="orders",
                    schema_name="public",
                    columns=[
                        Column(name="id", type="integer", nullable=False, primary_key=True),
                    ],
                )
            ]
        )
        with pytest.raises(PolicySchemaConflictError):
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT id FROM orders",
                row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                schema=schema,
                user_context=_USER,
                dialect=dialect,
            )

    @pytest.mark.parametrize("dialect", _DIALECTS)
    def test_drift_error_does_not_leak_column_name(self, dialect: str) -> None:
        """PolicySchemaConflictError message does not reveal the missing column."""
        schema = SchemaContext(
            tables=[
                Table(
                    name="orders",
                    schema_name="public",
                    columns=[
                        Column(name="id", type="integer", nullable=False, primary_key=True),
                    ],
                )
            ]
        )
        with pytest.raises(PolicySchemaConflictError) as exc_info:
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT id FROM orders",
                row_filters=[{"table": "orders", "filter": "secret_column = {user.role}"}],
                schema=schema,
                user_context=_USER,
                dialect=dialect,
            )
        err_str = str(exc_info.value)
        assert "secret_column" not in err_str
        assert "orders" not in err_str.lower() or "policyschemaconflict" in err_str.lower()


# ---------------------------------------------------------------------------
# T-762/T-763/T-764: Column masking per dialect (dialect-agnostic)
# ---------------------------------------------------------------------------


class TestColumnMaskingPerDialect:
    """Column masking is dialect-agnostic post-query replacement."""

    @pytest.mark.parametrize("dialect", _DIALECTS)
    def test_masked_columns_replaced_with_stars(self, dialect: str) -> None:
        """Masked column values are replaced with '***'."""
        result = _make_result()
        masked = PolicyEnforcementService.apply_column_masks(
            result=result,
            column_masks=[{"table": "orders", "columns": ["ssn"]}],
        )
        ssn_idx = next(i for i, c in enumerate(masked.columns) if c.name == "ssn")
        for row in masked.rows:
            assert row[ssn_idx] == "***"

    @pytest.mark.parametrize("dialect", _DIALECTS)
    def test_masked_column_meta_flag_set(self, dialect: str) -> None:
        """ColumnMeta.masked is True for masked columns."""
        result = _make_result()
        masked = PolicyEnforcementService.apply_column_masks(
            result=result,
            column_masks=[{"table": "orders", "columns": ["ssn"]}],
        )
        ssn_col = next(c for c in masked.columns if c.name == "ssn")
        assert ssn_col.masked is True
        id_col = next(c for c in masked.columns if c.name == "id")
        assert id_col.masked is False

    @pytest.mark.parametrize("dialect", _DIALECTS)
    def test_no_raw_value_leak_after_masking(self, dialect: str) -> None:
        """No raw sensitive value appears anywhere in the masked result."""
        result = _make_result()
        masked = PolicyEnforcementService.apply_column_masks(
            result=result,
            column_masks=[{"table": "orders", "columns": ["ssn"]}],
        )
        sensitive_values = {"111-11-1111", "222-22-2222", "333-33-3333"}
        all_cells = []
        for row in masked.rows:
            for cell in row:
                if isinstance(cell, str):
                    all_cells.append(cell)
        for val in sensitive_values:
            assert val not in " ".join(all_cells)


# ---------------------------------------------------------------------------
# T-762/T-763/T-764: Schema filtering (unauthorized tables/columns)
# ---------------------------------------------------------------------------


class TestSchemaFilteringPerDialect:
    """Unauthorized tables/columns never enter LLM schema context."""

    def test_unauthorized_table_excluded(self) -> None:
        """Tables not in policy are excluded from filtered schema."""
        schema = _make_schema()
        filtered = PolicyEnforcementService.filter_schema(
            schema=schema,
            allowed_tables=[{"table": "orders", "columns": ["id", "region"]}],
        )
        table_names = [t.name for t in filtered.tables]
        assert "orders" in table_names
        assert "secret_table" not in table_names

    def test_unauthorized_columns_excluded(self) -> None:
        """Columns not in policy are excluded from the allowed table."""
        schema = _make_schema()
        filtered = PolicyEnforcementService.filter_schema(
            schema=schema,
            allowed_tables=[{"table": "orders", "columns": ["id", "region"]}],
        )
        orders = next(t for t in filtered.tables if t.name == "orders")
        col_names = [c.name for c in orders.columns]
        assert "id" in col_names
        assert "region" in col_names
        assert "ssn" not in col_names
        assert "customer_email" not in col_names

    def test_none_policy_returns_empty_schema(self) -> None:
        """None policy is fail-closed: empty schema."""
        schema = _make_schema()
        filtered = PolicyEnforcementService.filter_schema(schema=schema, allowed_tables=None)
        assert filtered.tables == []

    def test_empty_policy_returns_empty_schema(self) -> None:
        """Empty list policy is fail-closed: empty schema."""
        schema = _make_schema()
        filtered = PolicyEnforcementService.filter_schema(schema=schema, allowed_tables=[])
        assert filtered.tables == []
