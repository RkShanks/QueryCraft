"""Tests for T-702: ``{user.*}`` placeholder binding.

Covers FR-131 / S-004. The binding step translates an admin-authored
filter fragment (already validated by ``validate_row_filter``) into
dialect-appropriate parameterized SQL.

Dialect placeholder styles:
- postgres / asyncpg: ``$1``, ``$2``, ... (numbered, ``start_index`` configurable)
- mysql / asyncmy: ``%s`` (positional)
- mssql / aioodbc: ``?`` (positional)
"""

from __future__ import annotations

import pytest

from app.services.policy_enforcement import (
    BoundSql,
    PolicyEnforcementService,
)

USER_FULL = {
    "email": "alice@example.com",
    "subject_id": "sso|abc-123",
    "role": "analyst",
}


# ──────────────────────────── BoundSql dataclass ────────────────────────────


class TestBoundSqlShape:
    def test_is_frozen_dataclass(self) -> None:
        bs = BoundSql(sql="SELECT 1", params=())
        with pytest.raises((AttributeError, Exception)):
            bs.sql = "SELECT 2"  # type: ignore[misc]

    def test_params_is_tuple(self) -> None:
        bs = PolicyEnforcementService.bind_placeholders("id = {user.email}", USER_FULL)
        assert isinstance(bs.params, tuple)

    def test_sql_and_params_are_strings_and_tuple(self) -> None:
        bs = PolicyEnforcementService.bind_placeholders("id = {user.email}", USER_FULL)
        assert isinstance(bs.sql, str)


# ──────────────────────────── Postgres dialect ────────────────────────────


class TestPostgresBinding:
    def test_email_placeholder_binds_to_param(self) -> None:
        result = PolicyEnforcementService.bind_placeholders(
            "owner_email = {user.email}", USER_FULL, dialect="postgres"
        )
        assert result.sql == "owner_email = $1"
        assert result.params == ("alice@example.com",)

    def test_subject_id_binds_to_param(self) -> None:
        result = PolicyEnforcementService.bind_placeholders(
            "owner_id = {user.subject_id}", USER_FULL, dialect="postgres"
        )
        assert result.sql == "owner_id = $1"
        assert result.params == ("sso|abc-123",)

    def test_role_binds_to_param(self) -> None:
        result = PolicyEnforcementService.bind_placeholders(
            "region = {user.role}", USER_FULL, dialect="postgres"
        )
        assert result.sql == "region = $1"
        assert result.params == ("analyst",)

    def test_repeated_placeholders_increment_index(self) -> None:
        """Same placeholder appearing twice must reference the same param
        (sqlglot-equivalent semantics) OR each occurrence get its own
        sequential number. We choose sequential: ``$1`` then ``$2`` with
        the same value bound twice — drivers treat this as two distinct
        binds. Either choice is fine; this test pins our choice.
        """
        result = PolicyEnforcementService.bind_placeholders(
            "a = {user.email} OR b = {user.email}", USER_FULL, dialect="postgres"
        )
        assert result.sql == "a = $1 OR b = $2"
        assert result.params == ("alice@example.com", "alice@example.com")

    def test_distinct_placeholders_increment_index(self) -> None:
        result = PolicyEnforcementService.bind_placeholders(
            "region = {user.role} AND owner = {user.email}",
            USER_FULL,
            dialect="postgres",
        )
        assert result.sql == "region = $1 AND owner = $2"
        assert result.params == ("analyst", "alice@example.com")

    def test_start_index_two(self) -> None:
        """``start_index=2`` so existing SQL using ``$1`` can be concatenated
        after. The fragment's placeholders must begin at the requested index.
        """
        result = PolicyEnforcementService.bind_placeholders(
            "region = {user.role}", USER_FULL, dialect="postgres", start_index=2
        )
        assert result.sql == "region = $2"
        assert result.params == ("analyst",)

    def test_start_index_ten(self) -> None:
        result = PolicyEnforcementService.bind_placeholders(
            "a = {user.email} AND b = {user.role}",
            USER_FULL,
            dialect="postgres",
            start_index=10,
        )
        assert result.sql == "a = $10 AND b = $11"
        assert result.params == ("alice@example.com", "analyst")

    def test_no_placeholders_returns_unmodified_sql(self) -> None:
        result = PolicyEnforcementService.bind_placeholders(
            "region = 'US'", USER_FULL, dialect="postgres"
        )
        assert result.sql == "region = 'US'"
        assert result.params == ()


# ──────────────────────────── MySQL dialect ────────────────────────────


class TestMySQLBinding:
    def test_email_uses_percent_s(self) -> None:
        result = PolicyEnforcementService.bind_placeholders(
            "owner_email = {user.email}", USER_FULL, dialect="mysql"
        )
        assert result.sql == "owner_email = %s"
        assert result.params == ("alice@example.com",)

    def test_distinct_placeholders_use_distinct_params(self) -> None:
        result = PolicyEnforcementService.bind_placeholders(
            "region = {user.role} AND owner = {user.email}",
            USER_FULL,
            dialect="mysql",
        )
        assert result.sql == "region = %s AND owner = %s"
        assert result.params == ("analyst", "alice@example.com")

    def test_repeated_placeholders_emit_distinct_params(self) -> None:
        result = PolicyEnforcementService.bind_placeholders(
            "a = {user.email} OR b = {user.email}", USER_FULL, dialect="mysql"
        )
        assert result.sql == "a = %s OR b = %s"
        assert result.params == ("alice@example.com", "alice@example.com")

    def test_start_index_ignored_for_mysql(self) -> None:
        """MySQL uses positional ``%s``; start_index is a no-op for non-Postgres."""
        result = PolicyEnforcementService.bind_placeholders(
            "region = {user.role}", USER_FULL, dialect="mysql", start_index=99
        )
        assert result.sql == "region = %s"
        assert result.params == ("analyst",)


# ──────────────────────────── MSSQL dialect ────────────────────────────


class TestMSSQLBinding:
    def test_email_uses_question_mark(self) -> None:
        result = PolicyEnforcementService.bind_placeholders(
            "owner_email = {user.email}", USER_FULL, dialect="mssql"
        )
        assert result.sql == "owner_email = ?"
        assert result.params == ("alice@example.com",)

    def test_distinct_placeholders_use_distinct_params(self) -> None:
        result = PolicyEnforcementService.bind_placeholders(
            "region = {user.role} AND owner = {user.email}",
            USER_FULL,
            dialect="mssql",
        )
        assert result.sql == "region = ? AND owner = ?"
        assert result.params == ("analyst", "alice@example.com")

    def test_repeated_placeholders_emit_distinct_params(self) -> None:
        result = PolicyEnforcementService.bind_placeholders(
            "a = {user.email} OR b = {user.email}", USER_FULL, dialect="mssql"
        )
        assert result.sql == "a = ? OR b = ?"
        assert result.params == ("alice@example.com", "alice@example.com")


# ──────────────────────────── Failure modes ────────────────────────────


class TestBindingFailures:
    def test_unknown_placeholder_rejected(self) -> None:
        with pytest.raises(ValueError, match="placeholder_binding_failed"):
            PolicyEnforcementService.bind_placeholders(
                "x = {user.tenant}", USER_FULL, dialect="postgres"
            )

    def test_missing_email_value_rejected(self) -> None:
        ctx = {"subject_id": "sso|x", "role": "analyst"}
        with pytest.raises(ValueError, match="placeholder_binding_failed"):
            PolicyEnforcementService.bind_placeholders(
                "owner_email = {user.email}", ctx, dialect="postgres"
            )

    def test_missing_subject_id_value_rejected(self) -> None:
        ctx = {"email": "a@b.c", "role": "analyst"}
        with pytest.raises(ValueError, match="placeholder_binding_failed"):
            PolicyEnforcementService.bind_placeholders(
                "owner = {user.subject_id}", ctx, dialect="postgres"
            )

    def test_missing_role_value_rejected(self) -> None:
        ctx = {"email": "a@b.c", "subject_id": "sso|x"}
        with pytest.raises(ValueError, match="placeholder_binding_failed"):
            PolicyEnforcementService.bind_placeholders(
                "region = {user.role}", ctx, dialect="postgres"
            )

    def test_empty_user_context_rejected(self) -> None:
        with pytest.raises(ValueError, match="placeholder_binding_failed"):
            PolicyEnforcementService.bind_placeholders(
                "region = {user.role}", {}, dialect="postgres"
            )

    def test_none_user_value_rejected(self) -> None:
        with pytest.raises(ValueError, match="placeholder_binding_failed"):
            PolicyEnforcementService.bind_placeholders(
                "region = {user.role}", {"email": "a@b.c", "subject_id": "x", "role": None},
                dialect="postgres",
            )

    def test_raw_user_value_does_not_appear_in_sql(self) -> None:
        """Hard guarantee: even if a user value contains SQL metacharacters,
        the output SQL must not contain it — the value lives only in params.
        """
        ctx = {"email": "evil'; DROP TABLE users;--", "subject_id": "x", "role": "analyst"}
        result = PolicyEnforcementService.bind_placeholders(
            "owner_email = {user.email}", ctx, dialect="postgres"
        )
        assert "evil" not in result.sql
        assert "DROP" not in result.sql
        assert "--" not in result.sql
        assert result.params == ("evil'; DROP TABLE users;--",)

    def test_raw_user_value_quoted_in_mysql(self) -> None:
        ctx = {"email": "weird'value", "subject_id": "x", "role": "analyst"}
        result = PolicyEnforcementService.bind_placeholders(
            "owner_email = {user.email}", ctx, dialect="mysql"
        )
        assert "weird" not in result.sql
        assert "value" not in result.sql
        assert result.sql == "owner_email = %s"
        assert result.params == ("weird'value",)
