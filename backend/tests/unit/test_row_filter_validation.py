"""Tests for PolicyEnforcementService.validate_row_filter (T-700).

Row filter validation at save time (S-004, FR-131). Wraps the admin-authored
fragment as ``SELECT 1 WHERE <filter>`` and parses with sqlglot to reject
dangerous expressions and validate column existence against the target table.

Placeholder syntax (``{user.email}``, ``{user.subject_id}``, ``{user.role}``) is
allowed syntactically but not bound here; T-702/T-704 cover binding/injection.
"""

from __future__ import annotations

import copy

import pytest

from app.evaluator.schema_context import Column, SchemaContext, Table
from app.services.policy_enforcement import PolicyEnforcementService


def _build_orders_schema() -> SchemaContext:
    """Schema with a single ``orders`` table spanning the typical columns."""
    return SchemaContext(
        tables=[
            Table(
                name="orders",
                schema_name="public",
                columns=[
                    Column(name="id", type="integer", nullable=False, primary_key=True),
                    Column(name="region", type="text", nullable=False),
                    Column(name="status", type="text", nullable=True),
                    Column(name="customer_id", type="integer", nullable=False),
                    Column(name="total", type="numeric", nullable=True),
                ],
            ),
        ]
    )


class TestValidateRowFilterAcceptsValidFilters:
    """Filters referencing existing columns with simple comparisons/boolean logic."""

    def test_simple_equality_filter_is_accepted(self) -> None:
        schema = _build_orders_schema()
        PolicyEnforcementService.validate_row_filter(
            "region = 'Sales'", schema, "orders"
        )

    def test_boolean_and_filter_is_accepted(self) -> None:
        schema = _build_orders_schema()
        PolicyEnforcementService.validate_row_filter(
            "region = 'Sales' AND status = 'active'", schema, "orders"
        )

    def test_boolean_or_filter_is_accepted(self) -> None:
        schema = _build_orders_schema()
        PolicyEnforcementService.validate_row_filter(
            "region = 'Sales' OR region = 'Marketing'", schema, "orders"
        )

    def test_parenthesized_boolean_filter_is_accepted(self) -> None:
        schema = _build_orders_schema()
        PolicyEnforcementService.validate_row_filter(
            "(region = 'Sales' OR region = 'Marketing') AND status = 'active'",
            schema,
            "orders",
        )

    def test_numeric_comparison_is_accepted(self) -> None:
        schema = _build_orders_schema()
        PolicyEnforcementService.validate_row_filter(
            "total > 100", schema, "orders"
        )

    def test_literal_only_filter_is_accepted(self) -> None:
        """A tautological filter (e.g. ``1 = 1``) is valid SQL and is allowed."""
        schema = _build_orders_schema()
        PolicyEnforcementService.validate_row_filter("1 = 1", schema, "orders")


class TestValidateRowFilterAcceptsAllowedPlaceholders:
    """The three documented placeholders are allowed syntactically."""

    def test_user_email_placeholder_is_accepted(self) -> None:
        schema = _build_orders_schema()
        PolicyEnforcementService.validate_row_filter(
            "customer_id = {user.subject_id}", schema, "orders"
        )

    def test_user_subject_id_placeholder_is_accepted(self) -> None:
        schema = _build_orders_schema()
        PolicyEnforcementService.validate_row_filter(
            "customer_id = {user.subject_id}", schema, "orders"
        )

    def test_user_role_placeholder_is_accepted(self) -> None:
        schema = _build_orders_schema()
        PolicyEnforcementService.validate_row_filter(
            "region = {user.role}", schema, "orders"
        )

    def test_multiple_placeholders_in_one_filter_are_accepted(self) -> None:
        schema = _build_orders_schema()
        PolicyEnforcementService.validate_row_filter(
            "region = {user.role} AND customer_id = {user.subject_id}",
            schema,
            "orders",
        )


class TestValidateRowFilterRejectsInvalidSQL:
    """Malformed fragments are rejected regardless of column references."""

    def test_garbage_input_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "this is not sql", schema, "orders"
            )

    def test_empty_filter_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter("", schema, "orders")

    def test_whitespace_only_filter_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter("   ", schema, "orders")

    def test_unbalanced_parens_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "(region = 'Sales'", schema, "orders"
            )


class TestValidateRowFilterRejectsMissingTable:
    """Target table must exist in the schema (fail-closed)."""

    def test_unknown_target_table_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "region = 'Sales'", schema, "nonexistent_table"
            )

    def test_empty_schema_is_rejected(self) -> None:
        schema = SchemaContext(tables=[])
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "1 = 1", schema, "orders"
            )


class TestValidateRowFilterRejectsNonexistentColumn:
    """Filter columns must exist in the target table."""

    def test_nonexistent_column_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "nonexistent_col = 'x'", schema, "orders"
            )

    def test_column_from_other_table_is_rejected(self) -> None:
        """A column reference qualified with a different table is rejected."""
        schema = SchemaContext(
            tables=[
                Table(
                    name="orders",
                    schema_name="public",
                    columns=[
                        Column(name="id", type="integer", nullable=False),
                        Column(name="region", type="text", nullable=False),
                    ],
                ),
                Table(
                    name="customers",
                    schema_name="public",
                    columns=[
                        Column(name="id", type="integer", nullable=False),
                        Column(name="name", type="text", nullable=True),
                    ],
                ),
            ]
        )
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "customers.name = 'x'", schema, "orders"
            )


class TestValidateRowFilterRejectsSubquery:
    """Subqueries under the WHERE clause are rejected (no nested SELECTs)."""

    def test_subquery_in_where_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "region IN (SELECT region FROM orders WHERE total > 100)",
                schema,
                "orders",
            )

    def test_subquery_as_value_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "region = (SELECT region FROM orders LIMIT 1)", schema, "orders"
            )


class TestValidateRowFilterRejectsFunctionCall:
    """All function calls are rejected (fail-closed; T-702 may relax to allowlist)."""

    def test_lowercase_function_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "region = LOWER('Sales')", schema, "orders"
            )

    def test_coalesce_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "COALESCE(status, 'unknown') = 'active'", schema, "orders"
            )

    def test_aggregate_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "total > AVG(total)", schema, "orders"
            )

    def test_current_user_is_rejected(self) -> None:
        """``current_user`` is a special sqlglot node (not exp.Anonymous)."""
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "region = current_user", schema, "orders"
            )


class TestValidateRowFilterRejectsSetOperations:
    """UNION/INTERSECT/EXCEPT are not legal in a row filter fragment."""

    def test_union_in_filter_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "region = 'Sales' UNION SELECT region FROM orders",
                schema,
                "orders",
            )

    def test_intersect_in_filter_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "region = 'Sales' INTERSECT SELECT region FROM orders",
                schema,
                "orders",
            )

    def test_except_in_filter_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "region = 'Sales' EXCEPT SELECT region FROM orders",
                schema,
                "orders",
            )


class TestValidateRowFilterRejectsDMLAndMultipleStatements:
    """DML/DDL and stacked statements are not legal in a row filter fragment."""

    def test_delete_statement_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "1 = 1; DELETE FROM orders", schema, "orders"
            )

    def test_update_statement_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "1 = 1; UPDATE orders SET status = 'x'", schema, "orders"
            )

    def test_insert_statement_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "1 = 1; INSERT INTO orders (id) VALUES (1)", schema, "orders"
            )

    def test_drop_statement_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "1 = 1; DROP TABLE orders", schema, "orders"
            )


class TestValidateRowFilterRejectsComments:
    """SQL comments are not allowed in a row filter fragment."""

    def test_inline_comment_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "region = 'Sales' -- trusted condition", schema, "orders"
            )

    def test_block_comment_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "region = 'Sales' /* trusted */", schema, "orders"
            )

    def test_comment_at_start_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "-- comment\nregion = 'Sales'", schema, "orders"
            )


class TestValidateRowFilterRejectsUnknownPlaceholder:
    """Only ``{user.email}``, ``{user.subject_id}``, ``{user.role}`` are allowed."""

    def test_unknown_user_attribute_is_rejected(self) -> None:
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "region = {user.evil}", schema, "orders"
            )

    def test_other_namespace_placeholder_is_rejected(self) -> None:
        """``{other.thing}`` is not a supported placeholder shape."""
        schema = _build_orders_schema()
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "region = {other.thing}", schema, "orders"
            )


class TestValidateRowFilterColumnMatchingCaseInsensitive:
    """Column matching is case-insensitive, consistent with SchemaContext."""

    def test_uppercase_column_is_accepted(self) -> None:
        schema = _build_orders_schema()
        PolicyEnforcementService.validate_row_filter(
            "REGION = 'Sales'", schema, "orders"
        )

    def test_mixed_case_column_is_accepted(self) -> None:
        schema = _build_orders_schema()
        PolicyEnforcementService.validate_row_filter(
            "Region = 'Sales' AND Status = 'active'", schema, "orders"
        )


class TestValidateRowFilterDoesNotMutateSchema:
    """The input SchemaContext must be returned untouched (immutability)."""

    def test_schema_is_not_mutated_on_success(self) -> None:
        schema = _build_orders_schema()
        snapshot = copy.deepcopy(schema)
        PolicyEnforcementService.validate_row_filter(
            "region = 'Sales'", schema, "orders"
        )
        assert schema == snapshot

    def test_schema_is_not_mutated_on_failure(self) -> None:
        schema = _build_orders_schema()
        snapshot = copy.deepcopy(schema)
        with pytest.raises(ValueError, match="filter_validation_failed"):
            PolicyEnforcementService.validate_row_filter(
                "nonexistent = 1", schema, "orders"
            )
        assert schema == snapshot


class TestValidateRowFilterErrorMessageIsSanitized:
    """Errors must not leak raw SQL, schema names, or driver internals."""

    def test_error_message_is_constant(self) -> None:
        """All validation failures raise the same opaque code (no leak)."""
        schema = _build_orders_schema()
        for bad in [
            "garbage",
            "nonexistent = 1",
            "region = LOWER('x')",
            "1 = 1; DROP TABLE x",
        ]:
            with pytest.raises(ValueError) as exc:
                PolicyEnforcementService.validate_row_filter(bad, schema, "orders")
            assert str(exc.value) == "filter_validation_failed"
