"""Seed local E2E source connections inside the platform database.

Idempotent support script for local/regression runs. It repairs the
configured PostgreSQL, MySQL, and MSSQL source connections, verifies
health, refreshes schema introspection, and grants the built-in Admin
role access to the introspected tables. It intentionally does not print
credentials.
"""

import asyncio
import os
import sys
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.credential_provider import FernetCredentialProvider
from app.db.models.connection_schema import ConnectionSchemaEntry
from app.db.models.database_connection import SourceDatabaseConnection
from app.db.models.enums import DatabaseType
from app.db.models.role import Role
from app.db.models.role_connection_policy import RoleConnectionPolicy
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.connection import ConnectionCreate
from app.services.connection_service import ConnectionService


@dataclass(frozen=True)
class SeedConnection:
    """Source connection values used by the deterministic local E2E seed."""

    display_name: str
    database_type: DatabaseType
    host: str
    port: int
    database_name: str
    username: str
    password: str
    ssl_mode: str = "disable"


async def main() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    settings = get_settings()
    specs = _build_seed_connections(settings)
    await _ensure_mssql_adventureworks()

    async with Session() as s:
        repo = ConnectionRepository(s)
        credential_provider = FernetCredentialProvider(settings.DB_CREDENTIAL_KEY)
        service = ConnectionService(
            repository=repo,
            credential_key=settings.DB_CREDENTIAL_KEY,
            get_db_session=lambda: s,
        )

        admin_role = await s.scalar(select(Role).where(Role.name == "Admin", Role.is_builtin.is_(True)).limit(1))
        if admin_role is None:
            raise RuntimeError("Built-in Admin role does not exist.")

        summaries = []
        for spec in specs:
            conn_model = await _upsert_connection(s, repo, credential_provider, service, spec)
            health = await service.test_connection(conn_model.id)
            if health.status != "healthy":
                raise RuntimeError(f"{spec.display_name} health check failed: {health.error_category or 'unknown'}")

            schema_result = await service.refresh_schema(conn_model.id)
            schema_entries = await repo.get_schema_entries(conn_model.id)
            if not schema_entries:
                raise RuntimeError(f"{spec.display_name} introspection completed without schema entries.")

            allowed_tables = _build_allowed_tables(schema_entries)
            await _upsert_admin_policy(s, admin_role, conn_model.id, allowed_tables)
            summaries.append(
                {
                    "display_name": spec.display_name,
                    "database_type": spec.database_type.value,
                    "health": health.status,
                    "schema_status": schema_result.get("status", "success"),
                    "tables": len(allowed_tables),
                    "columns": len(schema_entries),
                }
            )

        await s.commit()
        for summary in summaries:
            print(
                "Seeded local E2E connection: "
                f"name={summary['display_name']}, "
                f"type={summary['database_type']}, "
                f"health={summary['health']}, "
                f"schema_status={summary['schema_status']}, "
                f"tables={summary['tables']}, "
                f"columns={summary['columns']}, "
                "admin_policy=present."
            )


async def _upsert_connection(
    db_session,
    repo: ConnectionRepository,
    credential_provider: FernetCredentialProvider,
    service: ConnectionService,
    spec: SeedConnection,
) -> SourceDatabaseConnection:
    existing = await db_session.scalar(
        select(SourceDatabaseConnection)
        .where(
            SourceDatabaseConnection.display_name == spec.display_name,
            SourceDatabaseConnection.database_type == spec.database_type,
        )
        .order_by(SourceDatabaseConnection.created_at)
        .limit(1)
    )

    if existing:
        existing.host = spec.host
        existing.port = spec.port
        existing.database_name = spec.database_name
        existing.username = spec.username
        existing.encrypted_password = credential_provider.encrypt(spec.password)
        existing.ssl_mode = spec.ssl_mode
        conn_model = await repo.update(existing)
        print(f"Updated source connection '{spec.display_name}' from backend environment.")
        return conn_model

    req = ConnectionCreate(
        display_name=spec.display_name,
        database_type=spec.database_type,
        host=spec.host,
        port=spec.port,
        database_name=spec.database_name,
        username=spec.username,
        password=spec.password,
        ssl_mode=spec.ssl_mode,
    )
    created = await service.create(req)
    conn_model = await repo.get_by_id(created.id)
    if conn_model is None:
        raise RuntimeError(f"Created source connection '{spec.display_name}' could not be reloaded.")
    print(f"Created source connection '{spec.display_name}'.")
    return conn_model


async def _upsert_admin_policy(
    db_session,
    admin_role: Role,
    connection_id,
    allowed_tables: list[dict],
) -> None:
    policy = await db_session.scalar(
        select(RoleConnectionPolicy).where(
            RoleConnectionPolicy.role_id == admin_role.id,
            RoleConnectionPolicy.connection_id == connection_id,
        )
    )
    if policy is None:
        policy = RoleConnectionPolicy(
            role_id=admin_role.id,
            connection_id=connection_id,
            allowed_tables=allowed_tables,
            row_filters=[],
            column_masks=[],
        )
        db_session.add(policy)
    else:
        policy.allowed_tables = allowed_tables
        policy.row_filters = []
        policy.column_masks = []


def _build_seed_connections(settings) -> list[SeedConnection]:
    return [
        SeedConnection(
            display_name=settings.SOURCE_DB_NAME,
            database_type=DatabaseType.POSTGRESQL,
            host=settings.SOURCE_DB_HOST,
            port=settings.SOURCE_DB_PORT,
            database_name=settings.SOURCE_DB_NAME,
            username=settings.SOURCE_DB_USER,
            password=settings.SOURCE_DB_PASSWORD,
            ssl_mode=settings.SOURCE_DB_SSL_MODE,
        ),
        SeedConnection(
            display_name=_env("MYSQL_DISPLAY_NAME", "MySQL Sakila"),
            database_type=DatabaseType.MYSQL,
            host=_env("MYSQL_HOST", "mysql-source"),
            port=_env_int("MYSQL_PORT", 3306),
            database_name=_env("MYSQL_DATABASE", "sakila"),
            username=_required_env("MYSQL_USER"),
            password=_required_env("MYSQL_PASSWORD"),
            ssl_mode=_env("MYSQL_SSL_MODE", "disable"),
        ),
        SeedConnection(
            display_name=_env("MSSQL_DISPLAY_NAME", "MSSQL AdventureWorks"),
            database_type=DatabaseType.MSSQL,
            host=_env("MSSQL_HOST", "mssql-source"),
            port=_env_int("MSSQL_PORT", 1433),
            database_name=_env("MSSQL_DATABASE", "AdventureWorksLT"),
            username=_required_env("MSSQL_USER"),
            password=_required_env("MSSQL_PASSWORD"),
            ssl_mode=_env("MSSQL_SSL_MODE", "disable"),
        ),
    ]


async def _ensure_mssql_adventureworks() -> None:
    sa_password = os.environ.get("MSSQL_SA_PASSWORD")
    if not sa_password:
        raise RuntimeError("MSSQL_SA_PASSWORD is required to restore the local AdventureWorksLT fixture.")

    import aioodbc

    mssql_host = _env("MSSQL_HOST", "mssql-source")
    mssql_port = _env_int("MSSQL_PORT", 1433)
    mssql_user = _required_env("MSSQL_USER")
    mssql_password = _required_env("MSSQL_PASSWORD")
    login_name = _quote_mssql_identifier(mssql_user)
    login_literal = _quote_mssql_literal(mssql_user)
    password_literal = _quote_mssql_literal(mssql_password)
    restore_dsn = (
        f"DRIVER={{FreeTDS}};SERVER={mssql_host},{mssql_port};DATABASE=master;UID=sa;PWD={sa_password};TDS_Version=7.4;"
    )
    conn = await aioodbc.connect(dsn=restore_dsn, autocommit=True)
    try:
        async with conn.cursor() as cur:
            database_state = await _fetch_mssql_database_state(cur)
            if database_state and database_state != "ONLINE":
                await cur.execute("DROP DATABASE [AdventureWorksLT]")
                database_state = None
            if database_state is None:
                await cur.execute(
                    """
                    RESTORE DATABASE [AdventureWorksLT]
                    FROM DISK = N'/var/opt/mssql/backup/AdventureWorksLT2022.bak'
                    WITH MOVE N'AdventureWorksLT2022_Data' TO N'/var/opt/mssql/data/AdventureWorksLT.mdf',
                         MOVE N'AdventureWorksLT2022_Log' TO N'/var/opt/mssql/data/AdventureWorksLT_log.ldf',
                         REPLACE,
                         RECOVERY
                    """
                )
            await _wait_for_mssql_database_online(cur)
            await cur.execute(
                f"""
                IF NOT EXISTS (SELECT * FROM sys.server_principals WHERE name = {login_literal})
                BEGIN
                    CREATE LOGIN {login_name}
                    WITH PASSWORD = {password_literal},
                         DEFAULT_DATABASE = [AdventureWorksLT],
                         CHECK_EXPIRATION = OFF,
                         CHECK_POLICY = OFF
                END
                """
            )
            await cur.execute(
                f"""
                USE [AdventureWorksLT];
                IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = {login_literal})
                BEGIN
                    CREATE USER {login_name} FOR LOGIN {login_name}
                END
                """
            )
            await cur.execute(
                f"""
                USE [AdventureWorksLT];
                IF IS_ROLEMEMBER(N'db_datareader', {login_literal}) = 0
                BEGIN
                    ALTER ROLE [db_datareader] ADD MEMBER {login_name}
                END
                """
            )
    finally:
        await conn.close()
    print("Verified local MSSQL AdventureWorksLT fixture and read-only login.")


async def _fetch_mssql_database_state(cur) -> str | None:
    await cur.execute("SELECT state_desc FROM sys.databases WHERE name = N'AdventureWorksLT'")
    row = await cur.fetchone()
    return row[0] if row else None


async def _wait_for_mssql_database_online(cur) -> None:
    for _ in range(60):
        if await _fetch_mssql_database_state(cur) == "ONLINE":
            return
        await asyncio.sleep(1)
    raise RuntimeError("AdventureWorksLT database did not become online after restore.")


def _build_allowed_tables(schema_entries: list[ConnectionSchemaEntry]) -> list[dict]:
    columns_by_table: dict[str, list[str]] = defaultdict(list)
    for entry in schema_entries:
        columns_by_table[entry.table_name].append(entry.column_name)
    return [
        {"table": table_name, "columns": sorted(columns)}
        for table_name, columns in sorted(columns_by_table.items(), key=lambda item: item[0])
    ]


def _env(name: str, default: str) -> str:
    return os.environ.get(name) or default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required for local E2E source connection seeding.")
    return value


def _quote_mssql_identifier(value: str) -> str:
    return f"[{value.replace(']', ']]')}]"


def _quote_mssql_literal(value: str) -> str:
    return "N'" + value.replace("'", "''") + "'"


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
