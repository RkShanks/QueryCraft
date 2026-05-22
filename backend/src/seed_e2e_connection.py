"""Seed E2E connection inside platform database. Idempotent."""

import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models.database_connection import SourceDatabaseConnection
from app.db.models.enums import DatabaseType
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.connection import ConnectionCreate
from app.services.connection_service import ConnectionService


async def main() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    settings = get_settings()

    async with Session() as s:
        # Check if 'Local Pagila' already exists
        existing = await s.scalar(
            select(SourceDatabaseConnection).where(SourceDatabaseConnection.display_name == "Local Pagila")
        )
        if existing:
            print(f"Connection 'Local Pagila' already exists (id={existing.id}); no-op.")
            return

        repo = ConnectionRepository(s)
        service = ConnectionService(
            repository=repo,
            credential_key=settings.DB_CREDENTIAL_KEY,
            get_db_session=lambda: s,
        )

        req = ConnectionCreate(
            display_name="Local Pagila",
            database_type=DatabaseType.POSTGRESQL,
            host="127.0.0.1",
            port=5434,
            database_name="source_analytics",
            username="pagila_user",
            password="pagila_dev_pwd",
            ssl_mode="disable",
        )

        # Create connection via service. It will run health test and auto-introspection!
        created = await service.create(req)
        print(
            f"Created connection 'Local Pagila' (id={created.id}, "
            f"health={created.health_status}, "
            f"schema={created.schema_introspection_status})."
        )

        # Now, update the database connection host/port so that it's correct for docker network
        conn_model = await s.scalar(
            select(SourceDatabaseConnection).where(SourceDatabaseConnection.display_name == "Local Pagila")
        )
        if conn_model:
            conn_model.host = "postgres-source"
            conn_model.port = 5432
            await s.commit()
            print("Successfully updated connection host/port to docker network 'postgres-source:5432'")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
