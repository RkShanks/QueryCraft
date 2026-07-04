"""Seed the local E2E source connection inside the platform database.

Idempotent support script for local/regression runs. It repairs the
configured source connection, verifies health, refreshes schema
introspection, and grants the built-in Admin role access to the
introspected tables. It intentionally does not print credentials.
"""

import asyncio
import os
import sys
from collections import defaultdict

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


async def main() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    settings = get_settings()

    async with Session() as s:
        repo = ConnectionRepository(s)
        credential_provider = FernetCredentialProvider(settings.DB_CREDENTIAL_KEY)
        service = ConnectionService(
            repository=repo,
            credential_key=settings.DB_CREDENTIAL_KEY,
            get_db_session=lambda: s,
        )

        existing = await s.scalar(
            select(SourceDatabaseConnection)
            .where(SourceDatabaseConnection.display_name == settings.SOURCE_DB_NAME)
            .order_by(SourceDatabaseConnection.created_at)
            .limit(1)
        )

        if existing:
            existing.database_type = DatabaseType.POSTGRESQL
            existing.host = settings.SOURCE_DB_HOST
            existing.port = settings.SOURCE_DB_PORT
            existing.database_name = settings.SOURCE_DB_NAME
            existing.username = settings.SOURCE_DB_USER
            existing.encrypted_password = credential_provider.encrypt(settings.SOURCE_DB_PASSWORD)
            existing.ssl_mode = settings.SOURCE_DB_SSL_MODE
            conn_model = await repo.update(existing)
            print(f"Updated source connection '{settings.SOURCE_DB_NAME}' from backend environment.")
        else:
            req = ConnectionCreate(
                display_name=settings.SOURCE_DB_NAME,
                database_type=DatabaseType.POSTGRESQL,
                host=settings.SOURCE_DB_HOST,
                port=settings.SOURCE_DB_PORT,
                database_name=settings.SOURCE_DB_NAME,
                username=settings.SOURCE_DB_USER,
                password=settings.SOURCE_DB_PASSWORD,
                ssl_mode=settings.SOURCE_DB_SSL_MODE,
            )
            created = await service.create(req)
            conn_model = await repo.get_by_id(created.id)
            if conn_model is None:
                raise RuntimeError("Created source connection could not be reloaded.")
            print(f"Created source connection '{settings.SOURCE_DB_NAME}'.")

        health = await service.test_connection(conn_model.id)
        if health.status != "healthy":
            raise RuntimeError(f"Source connection health check failed: {health.error_category or 'unknown'}")

        schema_result = await service.refresh_schema(conn_model.id)
        schema_entries = await repo.get_schema_entries(conn_model.id)
        if not schema_entries:
            raise RuntimeError("Schema introspection completed without schema entries.")

        allowed_tables = _build_allowed_tables(schema_entries)

        admin_role = await s.scalar(select(Role).where(Role.name == "Admin", Role.is_builtin.is_(True)).limit(1))
        if admin_role is None:
            raise RuntimeError("Built-in Admin role does not exist.")

        policy = await s.scalar(
            select(RoleConnectionPolicy).where(
                RoleConnectionPolicy.role_id == admin_role.id,
                RoleConnectionPolicy.connection_id == conn_model.id,
            )
        )
        if policy is None:
            policy = RoleConnectionPolicy(
                role_id=admin_role.id,
                connection_id=conn_model.id,
                allowed_tables=allowed_tables,
                row_filters=[],
                column_masks=[],
            )
            s.add(policy)
        else:
            policy.allowed_tables = allowed_tables
            policy.row_filters = []
            policy.column_masks = []

        await s.commit()
        print(
            "Seeded local E2E connection: "
            f"health={health.status}, "
            f"schema_status={schema_result.get('status', 'success')}, "
            f"tables={len(allowed_tables)}, "
            f"columns={len(schema_entries)}, "
            "admin_policy=present."
        )


def _build_allowed_tables(schema_entries: list[ConnectionSchemaEntry]) -> list[dict]:
    columns_by_table: dict[str, list[str]] = defaultdict(list)
    for entry in schema_entries:
        columns_by_table[entry.table_name].append(entry.column_name)
    return [
        {"table": table_name, "columns": sorted(columns)}
        for table_name, columns in sorted(columns_by_table.items(), key=lambda item: item[0])
    ]


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
