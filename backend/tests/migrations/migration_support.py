"""Disposable PostgreSQL helpers for authoritative Alembic migration tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
ALEMBIC_DIR = BACKEND_ROOT / "alembic"
DISPOSABLE_DATABASE_PREFIX = "querycraft_migration_"
_DISPOSABLE_DATABASE_PATTERN = re.compile(r"querycraft_migration_[0-9a-f]{32}")


@dataclass(frozen=True)
class DatabaseSnapshot:
    """Value-safe schema and row-state proof for atomicity assertions."""

    revision: str | None
    schema_fingerprint: str
    row_counts: tuple[tuple[str, int], ...]
    row_fingerprints: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class TableSchema:
    """Structured table metadata used by schema-contract assertions."""

    name: str
    columns: tuple[tuple[str, str, bool, str | None], ...]
    primary_key: tuple[str, tuple[str, ...]]
    foreign_keys: tuple[tuple[object, ...], ...]
    unique_constraints: tuple[tuple[str, tuple[str, ...]], ...]
    indexes: tuple[tuple[object, ...], ...]


@dataclass(frozen=True)
class SchemaInventory:
    """Structured PostgreSQL schema inventory without row values."""

    tables: tuple[TableSchema, ...]

    @property
    def table_names(self) -> frozenset[str]:
        return frozenset(table.name for table in self.tables)

    def table(self, table_name: str) -> TableSchema:
        return next(table for table in self.tables if table.name == table_name)


def assert_disposable_database_url(database_url: str) -> URL:
    """Reject any migration target outside the dedicated database namespace."""
    parsed_url = make_url(database_url)
    database_name = parsed_url.database or ""
    if _DISPOSABLE_DATABASE_PATTERN.fullmatch(database_name) is None:
        raise RuntimeError("Migration test target is not a disposable database")
    return parsed_url


def alembic_config(database_url: str) -> Config:
    assert_disposable_database_url(database_url)
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def revision_ids() -> tuple[str, ...]:
    script = ScriptDirectory.from_config(alembic_config_for_history())
    return tuple(revision.revision for revision in reversed(list(script.walk_revisions())))


def alembic_config_for_history() -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    return config


def upgrade(database_url: str, target: str) -> None:
    command.upgrade(alembic_config(database_url), target)


def downgrade(database_url: str, target: str) -> None:
    assert_disposable_database_url(database_url)
    command.downgrade(alembic_config(database_url), target)


def create_disposable_database(admin_url: str, database_name: str) -> str:
    _assert_disposable_database_name(database_name)
    parsed_admin_url = make_url(admin_url)
    if parsed_admin_url.database != "postgres":
        raise RuntimeError("Migration test administrator must connect to the postgres database")
    asyncio.run(_create_database(parsed_admin_url, database_name))
    return parsed_admin_url.set(database=database_name).render_as_string(hide_password=False)


def drop_disposable_database(database_url: str) -> None:
    parsed_target_url = assert_disposable_database_url(database_url)
    admin_url = parsed_target_url.set(database="postgres")
    asyncio.run(_drop_database(admin_url, parsed_target_url.database or ""))


def current_revision(database_url: str) -> str | None:
    assert_disposable_database_url(database_url)
    return asyncio.run(_current_revision(database_url))


def database_snapshot(database_url: str) -> DatabaseSnapshot:
    assert_disposable_database_url(database_url)
    return asyncio.run(_database_snapshot(database_url))


def schema_inventory(database_url: str) -> SchemaInventory:
    assert_disposable_database_url(database_url)
    return asyncio.run(_schema_inventory(database_url))


def set_database_lock_timeout(database_url: str, timeout_milliseconds: int) -> None:
    parsed_url = assert_disposable_database_url(database_url)
    if timeout_milliseconds <= 0:
        raise RuntimeError("Migration test lock timeout must be positive")
    asyncio.run(_set_database_lock_timeout(parsed_url, timeout_milliseconds))


def _assert_disposable_database_name(database_name: str) -> None:
    if _DISPOSABLE_DATABASE_PATTERN.fullmatch(database_name) is None:
        raise RuntimeError("Migration test database name is not disposable")


async def _create_database(admin_url: URL, database_name: str) -> None:
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
    finally:
        await engine.dispose()


async def _drop_database(admin_url: URL, database_name: str) -> None:
    _assert_disposable_database_name(database_name)
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.exec_driver_sql(f'DROP DATABASE "{database_name}" WITH (FORCE)')
            database_exists = await connection.scalar(
                text("SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = :database_name)"),
                {"database_name": database_name},
            )
            if database_exists:
                raise RuntimeError("Disposable migration database survived cleanup")
    finally:
        await engine.dispose()


async def _current_revision(database_url: str) -> str | None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            version_table = await connection.scalar(text("SELECT to_regclass('public.alembic_version')"))
            if version_table is None:
                return None
            return await connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        await engine.dispose()


async def _database_snapshot(database_url: str) -> DatabaseSnapshot:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_snapshot_from_connection)
    finally:
        await engine.dispose()


async def _schema_inventory(database_url: str) -> SchemaInventory:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_schema_inventory_from_connection)
    finally:
        await engine.dispose()


async def _set_database_lock_timeout(database_url: URL, timeout_milliseconds: int) -> None:
    engine = create_async_engine(database_url, isolation_level="AUTOCOMMIT")
    database_name = database_url.database or ""
    _assert_disposable_database_name(database_name)
    try:
        async with engine.connect() as connection:
            await connection.exec_driver_sql(
                f"ALTER DATABASE \"{database_name}\" SET lock_timeout = '{timeout_milliseconds}ms'"
            )
    finally:
        await engine.dispose()


def _snapshot_from_connection(connection: Connection) -> DatabaseSnapshot:
    inventory = _schema_inventory_from_connection(connection)
    table_names = tuple(table.name for table in inventory.tables)
    schema_fingerprint = _fingerprint(inventory)
    row_counts = tuple((table_name, _row_count(connection, table_name)) for table_name in table_names)
    row_fingerprints = tuple((table_name, _row_fingerprint(connection, table_name)) for table_name in table_names)
    revision = _revision_from_connection(connection, table_names)
    return DatabaseSnapshot(revision, schema_fingerprint, row_counts, row_fingerprints)


def _schema_inventory_from_connection(connection: Connection) -> SchemaInventory:
    inspector = inspect(connection)
    tables = tuple(_table_schema(inspector, table_name) for table_name in sorted(inspector.get_table_names()))
    return SchemaInventory(tables)


def _table_schema(inspector, table_name: str) -> TableSchema:
    columns = tuple(
        sorted(
            (
                column["name"],
                str(column["type"]),
                bool(column["nullable"]),
                str(column["default"]) if column["default"] is not None else None,
            )
            for column in inspector.get_columns(table_name)
        )
    )
    return TableSchema(
        name=table_name,
        columns=columns,
        primary_key=_constraint_contract(inspector.get_pk_constraint(table_name)),
        foreign_keys=tuple(
            sorted(_foreign_key_contract(foreign_key) for foreign_key in inspector.get_foreign_keys(table_name))
        ),
        unique_constraints=tuple(
            sorted(_constraint_contract(constraint) for constraint in inspector.get_unique_constraints(table_name))
        ),
        indexes=tuple(sorted(_index_contract(index) for index in inspector.get_indexes(table_name))),
    )


def _constraint_contract(constraint: dict[str, object]) -> tuple[str, tuple[str, ...]]:
    columns = constraint.get("constrained_columns") or constraint.get("column_names") or ()
    return str(constraint.get("name") or ""), tuple(columns)


def _foreign_key_contract(foreign_key: dict[str, object]) -> tuple[object, ...]:
    return (
        str(foreign_key.get("name") or ""),
        tuple(foreign_key.get("constrained_columns") or ()),
        str(foreign_key.get("referred_table") or ""),
        tuple(foreign_key.get("referred_columns") or ()),
    )


def _index_contract(index: dict[str, object]) -> tuple[object, ...]:
    column_names: Sequence[str | None] = index.get("column_names") or ()
    return str(index.get("name") or ""), tuple(column_names), bool(index.get("unique"))


def _fingerprint(inventory: SchemaInventory) -> str:
    fingerprint_contract = [
        {
            "table": table.name,
            "columns": [(name, column_type) for name, column_type, _, _ in table.columns],
            "primary_key": table.primary_key,
            "foreign_keys": table.foreign_keys,
            "unique_constraints": table.unique_constraints,
            "indexes": table.indexes,
        }
        for table in inventory.tables
    ]
    canonical_schema = json.dumps(fingerprint_contract, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_schema.encode()).hexdigest()


def _quoted_table_name(connection: Connection, table_name: str) -> str:
    return connection.dialect.identifier_preparer.quote_identifier(table_name)


def _row_count(connection: Connection, table_name: str) -> int:
    quoted_table = _quoted_table_name(connection, table_name)
    return int(connection.exec_driver_sql(f"SELECT count(*) FROM {quoted_table}").scalar_one())


def _row_fingerprint(connection: Connection, table_name: str) -> str:
    quoted_table = _quoted_table_name(connection, table_name)
    statement = f"""
        SELECT md5(COALESCE(string_agg(row_fingerprint, '' ORDER BY row_fingerprint), ''))
        FROM (
            SELECT md5(to_jsonb(table_row)::text) AS row_fingerprint
            FROM {quoted_table} AS table_row
        ) AS row_fingerprints
    """
    return str(connection.exec_driver_sql(statement).scalar_one())


def _revision_from_connection(connection: Connection, table_names: tuple[str, ...]) -> str | None:
    if "alembic_version" not in table_names:
        return None
    return connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one_or_none()
