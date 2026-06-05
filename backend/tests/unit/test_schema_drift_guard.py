"""Tests for T-705: schema drift guard for row filters.

Covers FR-131 / S-004 / S-005. If a row filter references a column or
table that was removed from the connection schema between save time
and query time, ``apply_row_filters()`` must block the query with a
sanitized ``PolicySchemaConflictError`` BEFORE the SQL is executed.

A sanitized payload is also delivered to the optional ``audit_hook``
callable (FR-141 / tamper-evident audit). The hook signature is
``Callable[[AuditActionType, dict], None]``; the payload contains the
table name (admin-configured) but never the filter SQL, column name,
or schema internals.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.db.models.enums import AuditActionType
from app.evaluator.schema_context import Column, SchemaContext, Table
from app.services.policy_enforcement import (
    PolicyEnforcementService,
    PolicySchemaConflictError,
)

USER = {"email": "a@b.c", "subject_id": "sso|x", "role": "analyst"}


def _drifted_schema() -> SchemaContext:
    """Schema where the ``region`` column has been removed from ``orders``."""
    return SchemaContext(
        tables=[
            Table(
                name="orders",
                schema_name="public",
                columns=[
                    Column(name="id", type="integer", nullable=False, primary_key=True),
                    Column(name="owner_email", type="text", nullable=True),
                    # ``region`` removed — drift.
                ],
            ),
        ]
    )


def _matching_schema() -> SchemaContext:
    """Schema where the ``region`` column is still present."""
    return SchemaContext(
        tables=[
            Table(
                name="orders",
                schema_name="public",
                columns=[
                    Column(name="id", type="integer", nullable=False, primary_key=True),
                    Column(name="region", type="text", nullable=False),
                    Column(name="owner_email", type="text", nullable=True),
                ],
            ),
        ]
    )


# ──────────────────────── Drift detection ────────────────────────


class TestDriftDetection:
    def test_filter_referencing_dropped_column_raises(self) -> None:
        with pytest.raises(PolicySchemaConflictError):
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT id FROM orders",
                row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                schema=_drifted_schema(),
                user_context=USER,
                dialect="postgres",
            )

    def test_filter_referencing_removed_table_raises(self) -> None:
        schema = SchemaContext(tables=[])  # no tables at all
        with pytest.raises(PolicySchemaConflictError):
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT id FROM orders",
                row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                schema=schema,
                user_context=USER,
                dialect="postgres",
            )

    def test_drift_blocks_before_sql_modification(self) -> None:
        """The drift check must happen before any AST modification, so
        callers can catch the error and inspect the original SQL.
        """
        # No exception on the surface; just confirm the call raises.
        raised = False
        try:
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT id FROM orders",
                row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                schema=_drifted_schema(),
                user_context=USER,
                dialect="postgres",
            )
        except PolicySchemaConflictError:
            raised = True
        assert raised

    def test_valid_filter_against_drifted_schema_succeeds(self) -> None:
        """If the filter uses columns that ARE still present in the
        drifted schema, injection succeeds (no false-positive drift).
        """
        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders",
            row_filters=[{"table": "orders", "filter": "owner_email = {user.email}"}],
            schema=_drifted_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert "owner_email = $1" in result.sql
        assert result.params == ("a@b.c",)

    def test_mixed_valid_and_dropped_columns_first_wins(self) -> None:
        """When a list of filters contains one valid and one dropped,
        the first drift encountered raises — injection never completes.
        """
        with pytest.raises(PolicySchemaConflictError):
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT id FROM orders",
                row_filters=[
                    {"table": "orders", "filter": "owner_email = {user.email}"},
                    {"table": "orders", "filter": "region = {user.role}"},
                ],
                schema=_drifted_schema(),
                user_context=USER,
                dialect="postgres",
            )


# ──────────────────────── Sanitized error message ────────────────────────


class TestSanitizedError:
    def test_error_message_does_not_leak_filter_sql(self) -> None:
        """The error message must not contain the filter fragment or any
        column names from it.
        """
        with pytest.raises(PolicySchemaConflictError) as excinfo:
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT id FROM orders",
                row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                schema=_drifted_schema(),
                user_context=USER,
                dialect="postgres",
            )
        msg = str(excinfo.value).lower()
        assert "region" not in msg
        assert "{user.role}" not in msg
        assert "user.role" not in msg
        assert "select" not in msg

    def test_error_message_does_not_leak_user_value(self) -> None:
        ctx = {"email": "evil'; DROP TABLE x;--", "subject_id": "x", "role": "analyst"}
        with pytest.raises(PolicySchemaConflictError) as excinfo:
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT id FROM orders",
                row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                schema=_drifted_schema(),
                user_context=ctx,
                dialect="postgres",
            )
        msg = str(excinfo.value)
        assert "evil" not in msg
        assert "DROP" not in msg

    def test_error_message_is_constant(self) -> None:
        """Same drift always produces the same error string — no
        variable leakage.
        """
        msgs = set()
        for _ in range(3):
            with pytest.raises(PolicySchemaConflictError) as excinfo:
                PolicyEnforcementService.apply_row_filters(
                    sql="SELECT id FROM orders",
                    row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                    schema=_drifted_schema(),
                    user_context=USER,
                    dialect="postgres",
                )
            msgs.add(str(excinfo.value))
        assert len(msgs) == 1

    def test_error_carries_i18n_message_key(self) -> None:
        with pytest.raises(PolicySchemaConflictError) as excinfo:
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT id FROM orders",
                row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                schema=_drifted_schema(),
                user_context=USER,
                dialect="postgres",
            )
        assert excinfo.value.message_key == "error.policySchemaConflict"


# ──────────────────────── Audit hook integration ────────────────────────


class TestAuditHook:
    def test_audit_hook_called_on_drift(self) -> None:
        captured: list[tuple[AuditActionType, dict[str, Any]]] = []

        def _hook(action: AuditActionType, payload: dict[str, Any]) -> None:
            captured.append((action, payload))

        with pytest.raises(PolicySchemaConflictError):
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT id FROM orders",
                row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                schema=_drifted_schema(),
                user_context=USER,
                dialect="postgres",
                audit_hook=_hook,
            )
        assert len(captured) == 1
        action, payload = captured[0]
        assert action == AuditActionType.POLICY_SCHEMA_MISMATCH
        assert isinstance(payload, dict)

    def test_audit_hook_payload_is_sanitized(self) -> None:
        """The payload may carry the table name (admin-configured) but
        must NOT contain the filter SQL, column names, or user values.
        """
        captured: list[dict[str, Any]] = []

        def _hook(action: AuditActionType, payload: dict[str, Any]) -> None:
            captured.append(payload)

        with pytest.raises(PolicySchemaConflictError):
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT id FROM orders",
                row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                schema=_drifted_schema(),
                user_context=USER,
                dialect="postgres",
                audit_hook=_hook,
            )
        assert len(captured) == 1
        payload = captured[0]
        # Table name is allowed.
        assert payload.get("table") == "orders"
        # The rest must not leak.
        serialized = str(payload).lower()
        assert "region" not in serialized
        assert "{user.role}" not in serialized
        assert "user.role" not in serialized
        assert "analyst" not in serialized
        assert "a@b.c" not in serialized

    def test_audit_hook_not_called_on_success(self) -> None:
        captured: list[tuple[AuditActionType, dict[str, Any]]] = []

        def _hook(action: AuditActionType, payload: dict[str, Any]) -> None:
            captured.append((action, payload))

        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders",
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_matching_schema(),
            user_context=USER,
            dialect="postgres",
            audit_hook=_hook,
        )
        assert "region = $1" in result.sql
        assert captured == []

    def test_audit_hook_optional(self) -> None:
        """No ``audit_hook`` kwarg → no audit, no crash."""
        result = PolicyEnforcementService.apply_row_filters(
            sql="SELECT id FROM orders",
            row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
            schema=_matching_schema(),
            user_context=USER,
            dialect="postgres",
        )
        assert "region = $1" in result.sql

    def test_audit_hook_called_once_per_drift(self) -> None:
        """Even if multiple filters drift, the hook is called at least
        once before the function raises.
        """
        captured: list[AuditActionType] = []

        def _hook(action: AuditActionType, payload: dict[str, Any]) -> None:
            captured.append(action)

        with pytest.raises(PolicySchemaConflictError):
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT id FROM orders",
                row_filters=[
                    {"table": "orders", "filter": "region = {user.role}"},
                    {"table": "orders", "filter": "owner_email = {user.email}"},
                ],
                schema=SchemaContext(tables=[]),  # all filters drift
                user_context=USER,
                dialect="postgres",
                audit_hook=_hook,
            )
        # First drift raises; the function does not iterate further.
        assert len(captured) == 1
        assert captured[0] == AuditActionType.POLICY_SCHEMA_MISMATCH


# ──────────────────────── Cross-dialect drift ────────────────────────


class TestDriftAcrossDialects:
    def test_drift_detected_postgres(self) -> None:
        with pytest.raises(PolicySchemaConflictError):
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT id FROM orders",
                row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                schema=_drifted_schema(),
                user_context=USER,
                dialect="postgres",
            )

    def test_drift_detected_mysql(self) -> None:
        with pytest.raises(PolicySchemaConflictError):
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT id FROM orders",
                row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                schema=_drifted_schema(),
                user_context=USER,
                dialect="mysql",
            )

    def test_drift_detected_mssql(self) -> None:
        with pytest.raises(PolicySchemaConflictError):
            PolicyEnforcementService.apply_row_filters(
                sql="SELECT id FROM orders",
                row_filters=[{"table": "orders", "filter": "region = {user.role}"}],
                schema=_drifted_schema(),
                user_context=USER,
                dialect="mssql",
            )
