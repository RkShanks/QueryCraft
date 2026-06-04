"""Tests for PolicyEnforcementService.filter_schema (T-698).

Schema filtering service applies role policy to a SchemaContext, returning
a new SchemaContext containing only the allowed tables and columns. Used to
restrict the LLM prompt to role-permitted schema (S-006, FR-128, FR-129).
"""

from __future__ import annotations

import copy

import pytest

from app.evaluator.schema_context import Column, SchemaContext, Table
from app.services.policy_enforcement import PolicyEnforcementService


def _build_full_schema() -> SchemaContext:
    """Three-table schema spanning public + reporting with mixed columns."""
    return SchemaContext(
        tables=[
            Table(
                name="orders",
                schema_name="public",
                columns=[
                    Column(name="id", type="integer", nullable=False, primary_key=True),
                    Column(name="customer_id", type="integer", nullable=False),
                    Column(name="total", type="numeric", nullable=True),
                    Column(name="internal_notes", type="text", nullable=True),
                ],
            ),
            Table(
                name="customers",
                schema_name="public",
                columns=[
                    Column(name="id", type="integer", nullable=False, primary_key=True),
                    Column(name="name", type="text", nullable=True),
                    Column(name="email", type="text", nullable=True),
                    Column(name="ssn", type="text", nullable=True),
                ],
            ),
            Table(
                name="finance_summary",
                schema_name="reporting",
                columns=[
                    Column(name="region", type="text", nullable=False),
                    Column(name="revenue", type="numeric", nullable=True),
                ],
            ),
        ]
    )


class TestPolicyEnforcementServiceFilterSchemaTableFiltering:
    """Tables not present in the policy must be excluded from the result."""

    def test_disallowed_table_is_excluded(self) -> None:
        schema = _build_full_schema()
        policy = [{"table": "orders", "columns": ["id"]}]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        assert "orders" in [t.name for t in result.tables]
        assert "customers" not in [t.name for t in result.tables]
        assert "finance_summary" not in [t.name for t in result.tables]

    def test_multiple_allowed_tables_preserved(self) -> None:
        schema = _build_full_schema()
        policy = [
            {"table": "orders", "columns": ["id"]},
            {"table": "customers", "columns": ["id"]},
        ]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        names = {t.name for t in result.tables}
        assert names == {"orders", "customers"}


class TestPolicyEnforcementServiceFilterSchemaColumnFiltering:
    """Columns not present in the policy for an allowed table are excluded."""

    def test_disallowed_columns_inside_allowed_table_are_excluded(self) -> None:
        schema = _build_full_schema()
        policy = [{"table": "orders", "columns": ["id", "customer_id"]}]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        assert len(result.tables) == 1
        orders = result.tables[0]
        col_names = {c.name for c in orders.columns}
        assert col_names == {"id", "customer_id"}
        assert "total" not in col_names
        assert "internal_notes" not in col_names

    def test_all_columns_allowed_when_policy_lists_every_column(self) -> None:
        schema = _build_full_schema()
        policy = [
            {
                "table": "customers",
                "columns": ["id", "name", "email", "ssn"],
            }
        ]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        assert len(result.tables) == 1
        col_names = {c.name for c in result.tables[0].columns}
        assert col_names == {"id", "name", "email", "ssn"}


class TestPolicyEnforcementServiceFilterSchemaFailClosed:
    """Fail-closed semantics: no policy or empty policy must yield empty schema."""

    def test_none_policy_returns_empty_schema(self) -> None:
        schema = _build_full_schema()

        result = PolicyEnforcementService.filter_schema(schema, None)

        assert result.tables == []

    def test_empty_policy_list_returns_empty_schema(self) -> None:
        schema = _build_full_schema()

        result = PolicyEnforcementService.filter_schema(schema, [])

        assert result.tables == []

    def test_table_with_empty_columns_list_yields_table_with_no_columns(self) -> None:
        """A policy entry with columns=[] means the table is named but no columns are allowed."""
        schema = _build_full_schema()
        policy = [{"table": "orders", "columns": []}]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        assert len(result.tables) == 1
        assert result.tables[0].name == "orders"
        assert result.tables[0].columns == []


class TestPolicyEnforcementServiceFilterSchemaUnknownPolicyEntries:
    """Policy entries referencing tables/columns not in the schema are ignored silently (no leak)."""

    def test_policy_references_unknown_table_is_ignored(self) -> None:
        schema = _build_full_schema()
        policy = [
            {"table": "orders", "columns": ["id"]},
            {"table": "ghost_table", "columns": ["id", "name"]},
        ]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        names = {t.name for t in result.tables}
        assert names == {"orders"}
        assert "ghost_table" not in names

    def test_policy_references_unknown_column_in_known_table_is_ignored(self) -> None:
        schema = _build_full_schema()
        policy = [
            {
                "table": "orders",
                "columns": ["id", "phantom_column"],
            }
        ]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        assert len(result.tables) == 1
        col_names = {c.name for c in result.tables[0].columns}
        assert col_names == {"id"}
        assert "phantom_column" not in col_names

    def test_unknown_only_policy_returns_empty_schema(self) -> None:
        schema = _build_full_schema()
        policy = [{"table": "does_not_exist", "columns": ["id"]}]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        assert result.tables == []


class TestPolicyEnforcementServiceFilterSchemaMetadataPreservation:
    """The filter must preserve table schema_name and column metadata verbatim."""

    def test_table_schema_name_preserved(self) -> None:
        schema = _build_full_schema()
        policy = [{"table": "finance_summary", "columns": ["region"]}]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        assert len(result.tables) == 1
        assert result.tables[0].name == "finance_summary"
        assert result.tables[0].schema_name == "reporting"

    def test_column_metadata_preserved(self) -> None:
        schema = _build_full_schema()
        policy = [{"table": "orders", "columns": ["id", "internal_notes"]}]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        assert len(result.tables) == 1
        cols_by_name = {c.name: c for c in result.tables[0].columns}
        assert "id" in cols_by_name
        assert "internal_notes" in cols_by_name

        id_col = cols_by_name["id"]
        assert id_col.type == "integer"
        assert id_col.nullable is False
        assert id_col.primary_key is True

        notes_col = cols_by_name["internal_notes"]
        assert notes_col.type == "text"
        assert notes_col.nullable is True
        assert notes_col.primary_key is False


class TestPolicyEnforcementServiceFilterSchemaImmutability:
    """Input SchemaContext must not be mutated; result must be a new object."""

    def test_input_schema_not_mutated(self) -> None:
        schema = _build_full_schema()
        snapshot = copy.deepcopy(schema)
        policy = [{"table": "orders", "columns": ["id"]}]

        PolicyEnforcementService.filter_schema(schema, policy)

        assert schema.model_dump() == snapshot.model_dump()

    def test_returns_new_schema_context_instance(self) -> None:
        schema = _build_full_schema()
        policy = [{"table": "orders", "columns": ["id"]}]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        assert result is not schema
        assert isinstance(result, SchemaContext)

    def test_returned_tables_are_new_table_instances(self) -> None:
        schema = _build_full_schema()
        policy = [{"table": "orders", "columns": ["id"]}]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        original_table = schema.find_table("orders")
        result_table = result.find_table("orders")
        assert original_table is not None
        assert result_table is not None
        assert result_table is not original_table


class TestPolicyEnforcementServiceFilterSchemaCaseInsensitive:
    """Postgres folds unquoted identifiers to lowercase; matching is case-insensitive."""

    def test_policy_table_name_mixed_case_matches_lowercase_schema(self) -> None:
        schema = _build_full_schema()
        policy = [{"table": "ORDERS", "columns": ["id"]}]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        assert len(result.tables) == 1
        assert result.tables[0].name == "orders"

    def test_policy_column_name_mixed_case_matches_lowercase_schema(self) -> None:
        schema = _build_full_schema()
        policy = [{"table": "orders", "columns": ["ID", "Customer_ID"]}]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        col_names = {c.name for c in result.tables[0].columns}
        assert col_names == {"id", "customer_id"}


class TestPolicyEnforcementServiceFilterSchemaNoLeak:
    """The result must not expose unauthorized tables/columns under any allowed entry."""

    def test_no_disallowed_table_appears_in_any_result_table(self) -> None:
        schema = _build_full_schema()
        policy = [{"table": "orders", "columns": ["id", "customer_id"]}]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        names = {t.name for t in result.tables}
        assert "customers" not in names
        assert "finance_summary" not in names

    def test_no_disallowed_column_appears_in_any_result_table(self) -> None:
        schema = _build_full_schema()
        policy = [{"table": "orders", "columns": ["id"]}]

        result = PolicyEnforcementService.filter_schema(schema, policy)

        for table in result.tables:
            for column in table.columns:
                assert column.name in {"id"}


@pytest.fixture
def service() -> PolicyEnforcementService:
    """The service is stateless; this fixture documents the construction pattern."""
    return PolicyEnforcementService()
