"""Tests for deterministic local E2E source connection seeding."""

from types import SimpleNamespace

import pytest

from app.db.models.enums import DatabaseType
from seed_e2e_connection import (
    _build_seed_connections,
    _quote_mssql_identifier,
    _quote_mssql_literal,
    _required_env,
)


def test_build_seed_connections_includes_all_phase3_dialects(monkeypatch):
    monkeypatch.setenv("MYSQL_USER", "mysql_user")
    monkeypatch.setenv("MYSQL_PASSWORD", "mysql_password")
    monkeypatch.setenv("MSSQL_USER", "mssql_user")
    monkeypatch.setenv("MSSQL_PASSWORD", "mssql_password")

    settings = SimpleNamespace(
        SOURCE_DB_NAME="source_analytics",
        SOURCE_DB_HOST="postgres-source",
        SOURCE_DB_PORT=5432,
        SOURCE_DB_USER="pagila_user",
        SOURCE_DB_PASSWORD="pagila_password",
        SOURCE_DB_SSL_MODE="disable",
    )

    specs = _build_seed_connections(settings)

    assert [spec.database_type for spec in specs] == [
        DatabaseType.POSTGRESQL,
        DatabaseType.MYSQL,
        DatabaseType.MSSQL,
    ]
    assert [spec.display_name for spec in specs] == [
        "source_analytics",
        "MySQL Sakila",
        "MSSQL AdventureWorks",
    ]
    assert specs[1].host == "mysql-source"
    assert specs[1].database_name == "sakila"
    assert specs[2].host == "mssql-source"
    assert specs[2].database_name == "AdventureWorksLT"


def test_required_env_fails_closed_when_secret_env_missing(monkeypatch):
    monkeypatch.delenv("MYSQL_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="MYSQL_PASSWORD is required"):
        _required_env("MYSQL_PASSWORD")


def test_mssql_quoting_escapes_identifier_and_literal():
    assert _quote_mssql_identifier("user]name") == "[user]]name]"
    assert _quote_mssql_literal("pa'ss") == "N'pa''ss'"


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (None, ("restore",)),
        ("ONLINE", ()),
        ("RESTORING", ("drop", "restore")),
        ("RECOVERY_PENDING", ("drop", "restore")),
    ],
)
def test_plan_mssql_restore_actions_matrix(state, expected):
    from seed_e2e_connection import _plan_mssql_restore_actions

    assert _plan_mssql_restore_actions(state) == expected


async def test_mssql_host_with_dsn_metacharacters_rejected_before_connect(monkeypatch):
    monkeypatch.setenv("MSSQL_SA_PASSWORD", "sa-password")
    monkeypatch.setenv("MSSQL_USER", "mssql_user")
    monkeypatch.setenv("MSSQL_PASSWORD", "mssql-password")
    monkeypatch.setenv("MSSQL_HOST", "evil-host;PWD=inject")

    import seed_e2e_connection as seed

    with pytest.raises(RuntimeError, match="MSSQL_HOST"):
        await seed._ensure_mssql_adventureworks()


async def test_mssql_sa_password_with_dsn_separator_rejected_before_connect(monkeypatch):
    monkeypatch.setenv("MSSQL_SA_PASSWORD", "sa;PWD=inject")
    monkeypatch.setenv("MSSQL_USER", "mssql_user")
    monkeypatch.setenv("MSSQL_PASSWORD", "mssql-password")
    monkeypatch.delenv("MSSQL_HOST", raising=False)

    import seed_e2e_connection as seed

    with pytest.raises(RuntimeError, match="MSSQL_SA_PASSWORD"):
        await seed._ensure_mssql_adventureworks()


async def test_control_character_in_mssql_user_rejected_before_connect(monkeypatch):
    monkeypatch.setenv("MSSQL_SA_PASSWORD", "sa-password")
    monkeypatch.setenv("MSSQL_USER", "user\nname")
    monkeypatch.setenv("MSSQL_PASSWORD", "mssql-password")
    monkeypatch.delenv("MSSQL_HOST", raising=False)

    import seed_e2e_connection as seed

    with pytest.raises(RuntimeError, match="MSSQL_USER"):
        await seed._ensure_mssql_adventureworks()


async def test_connect_failure_raises_sanitized_error_without_dsn_or_secret(monkeypatch):
    monkeypatch.setenv("MSSQL_SA_PASSWORD", "super-secret-sa-value")
    monkeypatch.setenv("MSSQL_USER", "mssql_user")
    monkeypatch.setenv("MSSQL_PASSWORD", "mssql-password")
    monkeypatch.delenv("MSSQL_HOST", raising=False)

    import aioodbc

    import seed_e2e_connection as seed

    async def failing_connect(dsn, **kwargs):
        raise RuntimeError(f"driver exploded for dsn {dsn}")

    calls: list[str] = []

    async def spy_connect(dsn, **kwargs):
        calls.append(dsn)
        return await failing_connect(dsn, **kwargs)

    monkeypatch.setattr(aioodbc, "connect", spy_connect)

    with pytest.raises(RuntimeError) as raised:
        await seed._ensure_mssql_adventureworks()

    message = str(raised.value)
    assert "PWD" not in message
    assert "super-secret-sa-value" not in message
    assert "DRIVER" not in message
    assert len(calls) == 1
