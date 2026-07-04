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
