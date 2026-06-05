"""Tests for T-706: column masking service.

Covers FR-132 / SC-052. ``PolicyEnforcementService.apply_column_masks()``
operates on a ``QueryResult`` after execution (post-query, dialect-independent)
and replaces values in configured columns with ``"***"`` while setting
``ColumnMeta.masked = True`` for the affected columns.

Config shape (mirrors ``role_connection_policies.column_masks``):
    [{"table": "orders", "columns": ["ssn", "salary"]}]

Behaviour:
- Returns a NEW ``QueryResult``; the input is never mutated.
- Column matching is case-insensitive (postgres lower-folds, MySQL depends
  on collation, MSSQL is case-insensitive by default — admin config may
  differ in case from the result's column name).
- A configured column that is NOT present in the result is a silent no-op
  (no leak is possible because the value never reached the user).
- Malformed config (non-list, non-dict entries, missing ``table`` or
  ``columns`` key, wrong types) raises ``ValueError("column_mask_config_invalid")``
  — fail-closed. Error message is a constant and never echoes the
  offending config (no leak of admin policy or column names).
- Empty / ``None`` config returns an original-equivalent result (new
  instance, no masking, ``masked`` flag remains its default).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.query import ColumnMeta, QueryResult
from app.services.policy_enforcement import PolicyEnforcementService


def _result(
    columns: list[tuple[str, str]] | None = None,
    rows: list[list] | None = None,
) -> QueryResult:
    """Build a ``QueryResult`` with sensible defaults for masking tests."""
    if columns is None:
        columns = [("id", "integer"), ("email", "text"), ("ssn", "text")]
    if rows is None:
        rows = [
            [1, "alice@example.com", "111-22-3333"],
            [2, "bob@example.com", "444-55-6666"],
        ]
    return QueryResult(
        attempt_id="att-1",
        session_id="sess-1",
        question="q",
        generated_sql="SELECT id, email, ssn FROM users",
        columns=[ColumnMeta(name=n, type=t) for n, t in columns],
        rows=rows,
        row_count=len(rows),
        attempt_number=1,
        is_last_auto_retry=False,
    )


_MASKS = [{"table": "users", "columns": ["ssn"]}]


# ──────────────────────────── Mask value replacement ────────────────────────────


class TestMaskValueReplacement:
    def test_values_in_masked_column_replaced(self) -> None:
        out = PolicyEnforcementService.apply_column_masks(_result(), _MASKS)
        # All rows: ssn column (index 2) replaced with "***"
        assert all(row[2] == "***" for row in out.rows)
        # Unmasked columns preserved
        assert out.rows[0][0] == 1
        assert out.rows[0][1] == "alice@example.com"
        assert out.rows[1][0] == 2
        assert out.rows[1][1] == "bob@example.com"

    def test_unmasked_columns_preserved_unchanged(self) -> None:
        out = PolicyEnforcementService.apply_column_masks(_result(), _MASKS)
        for orig_row, out_row in zip(_result().rows, out.rows, strict=True):
            # id, email untouched
            assert out_row[0] == orig_row[0]
            assert out_row[1] == orig_row[1]

    def test_multiple_masked_columns_in_one_entry(self) -> None:
        masks = [{"table": "users", "columns": ["ssn", "email"]}]
        out = PolicyEnforcementService.apply_column_masks(_result(), masks)
        assert all(row[1] == "***" for row in out.rows)
        assert all(row[2] == "***" for row in out.rows)
        assert all(row[0] == orig[0] for orig, row in zip(_result().rows, out.rows, strict=True))

    def test_multiple_entries_accumulate(self) -> None:
        masks = [
            {"table": "users", "columns": ["ssn"]},
            {"table": "users", "columns": ["email"]},
        ]
        out = PolicyEnforcementService.apply_column_masks(_result(), masks)
        assert all(row[1] == "***" for row in out.rows)
        assert all(row[2] == "***" for row in out.rows)


# ──────────────────────────── ColumnMeta.masked flag ────────────────────────────


class TestMaskedFlag:
    def test_masked_flag_set_on_masked_column(self) -> None:
        out = PolicyEnforcementService.apply_column_masks(_result(), _MASKS)
        ssn = next(c for c in out.columns if c.name == "ssn")
        assert ssn.masked is True

    def test_masked_flag_default_false_on_unmasked_columns(self) -> None:
        out = PolicyEnforcementService.apply_column_masks(_result(), _MASKS)
        for col in out.columns:
            if col.name == "ssn":
                assert col.masked is True
            else:
                assert col.masked is False

    def test_masked_column_meta_preserves_type(self) -> None:
        out = PolicyEnforcementService.apply_column_masks(_result(), _MASKS)
        ssn = next(c for c in out.columns if c.name == "ssn")
        assert ssn.type == "text"
        assert ssn.name == "ssn"

    def test_columnmeta_has_default_masked_false(self) -> None:
        """Pydantic default: ``ColumnMeta(..., masked)`` defaults to False."""
        cm = ColumnMeta(name="x", type="text")
        assert cm.masked is False


# ──────────────────────────── Immutability / non-mutation ────────────────────────────


class TestImmutability:
    def test_input_result_not_mutated(self) -> None:
        original = _result()
        original_rows = [list(r) for r in original.rows]
        original_columns = [(c.name, c.type) for c in original.columns]
        PolicyEnforcementService.apply_column_masks(original, _MASKS)
        # Rows unchanged in place
        assert [list(r) for r in original.rows] == original_rows
        # Columns unchanged
        assert [(c.name, c.type) for c in original.columns] == original_columns
        # masked flag was never set on the input
        assert all(c.masked is False for c in original.columns)
        # Original row values still contain real SSNs
        assert "111-22-3333" in original.rows[0]
        assert "444-55-6666" in original.rows[1]

    def test_returns_new_query_result_instance(self) -> None:
        original = _result()
        out = PolicyEnforcementService.apply_column_masks(original, _MASKS)
        assert out is not original
        # columns/rows are independent list instances
        assert out.columns is not original.columns
        assert out.rows is not original.rows
        for o_row, n_row in zip(original.rows, out.rows, strict=True):
            assert o_row is not n_row

    def test_empty_mask_config_returns_original_equivalent(self) -> None:
        original = _result()
        for empty in (None, [], [{}]):
            out = PolicyEnforcementService.apply_column_masks(original, empty)
            assert out is not original
            # Same row values, same column metadata (all masked=False)
            assert out.rows == original.rows
            assert [(c.name, c.type, c.masked) for c in out.columns] == [
                (c.name, c.type, c.masked) for c in original.columns
            ]


# ──────────────────────────── Case-insensitive matching ────────────────────────────


class TestCaseInsensitiveMatching:
    def test_uppercase_config_matches_lowercase_column(self) -> None:
        masks = [{"table": "users", "columns": ["SSN"]}]
        out = PolicyEnforcementService.apply_column_masks(_result(), masks)
        assert all(row[2] == "***" for row in out.rows)
        ssn = next(c for c in out.columns if c.name == "ssn")
        assert ssn.masked is True

    def test_mixed_case_config(self) -> None:
        masks = [{"table": "users", "columns": ["Ssn", "EMAIL"]}]
        out = PolicyEnforcementService.apply_column_masks(_result(), masks)
        assert all(row[1] == "***" for row in out.rows)
        assert all(row[2] == "***" for row in out.rows)


# ──────────────────────────── Dialect independence ────────────────────────────


class TestDialectIndependence:
    """Masking operates on the post-execution ``QueryResult`` regardless of
    which dialect produced the rows. We only verify that the column name in
    the result is matched (case-insensitively) — dialect is not threaded
    through ``apply_column_masks``.
    """

    @pytest.mark.parametrize(
        "dialect",
        ["postgres", "mysql", "mssql"],
    )
    def test_masks_applied_for_each_dialect_result(self, dialect: str) -> None:
        # Simulate a dialect-typed result with dialect-specific column
        # name casing. All three should be masked.
        columns = [(f"{dialect}_id", "integer"), ("ssn", "text")]
        rows = [[1, "111-22-3333"], [2, "444-55-6666"]]
        r = _result(columns=columns, rows=rows)
        out = PolicyEnforcementService.apply_column_masks(r, _MASKS)
        assert all(row[1] == "***" for row in out.rows)
        assert out.rows[0][0] == 1

    def test_no_dialect_parameter_required(self) -> None:
        """``apply_column_masks`` signature does not accept a dialect param.
        Regression guard: if someone adds one, masking is no longer
        post-query-only.
        """
        import inspect

        sig = inspect.signature(PolicyEnforcementService.apply_column_masks)
        assert "dialect" not in sig.parameters


# ──────────────────────────── Unknown / malformed config ────────────────────────────


class TestUnknownAndMalformedConfig:
    def test_configured_column_not_in_result_is_silent_noop(self) -> None:
        """Rationale: a configured column that does not appear in the
        result set cannot leak — its value was never returned to the
        service. Silently ignoring it keeps the query path resilient
        when the LLM picks a different projection than the admin
        configured. Compare to the schema-drift guard (T-705), which
        runs at filter-injection time and DOES fail closed: there the
        filter is going to be injected, so a missing reference IS a
        security gap. Masking is output-time only.
        """
        masks = [{"table": "users", "columns": ["nonexistent_column"]}]
        out = PolicyEnforcementService.apply_column_masks(_result(), masks)
        # Nothing masked, all data preserved
        assert all(c.masked is False for c in out.columns)
        assert out.rows[0][2] == "111-22-3333"
        assert out.rows[1][2] == "444-55-6666"

    def test_empty_columns_in_entry_is_silent_noop(self) -> None:
        masks = [{"table": "users", "columns": []}]
        out = PolicyEnforcementService.apply_column_masks(_result(), masks)
        assert all(c.masked is False for c in out.columns)
        assert all(row[2] == "111-22-3333" or row[2] == "444-55-6666" for row in out.rows)

    @pytest.mark.parametrize(
        "bad_config",
        [
            "not-a-list-of-dicts",  # wrong top-level type
            [{"table": "users"}],  # missing 'columns'
            [{"columns": ["ssn"]}],  # missing 'table'
            [{"table": "", "columns": ["ssn"]}],  # empty table
            [{"table": "users", "columns": "ssn"}],  # columns not a list
            [{"table": 123, "columns": ["ssn"]}],  # table not a string
            [{"table": "users", "columns": [""]}],  # empty column name
            [{"table": "users", "columns": [123]}],  # column name not a string
        ],
    )
    def test_malformed_config_raises_sanitized_error(self, bad_config) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(ValueError) as excinfo:
            PolicyEnforcementService.apply_column_masks(_result(), bad_config)
        # Constant sanitized error code; never echoes the bad config
        assert excinfo.value.args[0] == "column_mask_config_invalid"
        # No leak: error message must not include column names or table names
        # from the bad config (other than the constant).
        msg = str(excinfo.value)
        assert "ssn" not in msg
        assert "users" not in msg
        assert "123" not in msg

    def test_malformed_config_does_not_leak_raw_value(self) -> None:
        """If a malformed config contains a sensitive value, that value
        must not appear in the error message.
        """
        bad = [{"table": "secret_table_xyz", "columns": ["super_secret_col_abc"]}]
        with pytest.raises(ValueError) as excinfo:
            PolicyEnforcementService.apply_column_masks(_result(), bad)
        msg = str(excinfo.value)
        assert "secret_table_xyz" not in msg
        assert "super_secret_col_abc" not in msg


# ──────────────────────────── Output never contains raw value ────────────────────────────


class TestNoSensitiveValueInOutput:
    def test_masked_value_does_not_appear_in_rows(self) -> None:
        original = _result()
        out = PolicyEnforcementService.apply_column_masks(original, _MASKS)
        for row in out.rows:
            for cell in row:
                assert cell != "111-22-3333"
                assert cell != "444-55-6666"

    def test_masked_value_does_not_appear_in_serialized_form(self) -> None:
        """Round-trip through Pydantic ``model_dump()`` to confirm the
        masked string is the only representation of the value in the
        output.
        """
        out = PolicyEnforcementService.apply_column_masks(_result(), _MASKS)
        dumped = out.model_dump()
        for row in dumped["rows"]:
            assert "111-22-3333" not in row
            assert "444-55-6666" not in row
            assert "***" in row  # the mask appears at least once

    def test_empty_rows_masked_produces_empty_rows(self) -> None:
        result = _result(rows=[])
        out = PolicyEnforcementService.apply_column_masks(result, _MASKS)
        assert out.rows == []
        assert out.row_count == 0
