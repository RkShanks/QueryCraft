"""Connection repository for SourceDatabaseConnection CRUD operations (FR-059)."""

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.connection_schema import ConnectionSchemaEntry
from app.db.models.database_connection import SourceDatabaseConnection


class ConnectionRepository:
    """Data access layer for SourceDatabaseConnection."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def create(self, connection: SourceDatabaseConnection) -> SourceDatabaseConnection:
        """Persist a new connection and return it with generated ID."""
        self._db_session.add(connection)
        await self._db_session.flush()
        await self._db_session.refresh(connection)
        return connection

    async def get_by_id(self, connection_id: uuid.UUID) -> SourceDatabaseConnection | None:
        """Fetch a connection by ID, or None if not found."""
        result = await self._db_session.execute(
            select(SourceDatabaseConnection).where(SourceDatabaseConnection.id == connection_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[SourceDatabaseConnection]:
        """Return all connections."""
        result = await self._db_session.execute(select(SourceDatabaseConnection))
        return list(result.scalars().all())

    async def update(self, connection: SourceDatabaseConnection) -> SourceDatabaseConnection:
        """Update an existing connection."""
        await self._db_session.flush()
        await self._db_session.refresh(connection)
        return connection

    async def delete(self, connection_id: uuid.UUID) -> None:
        """Delete a connection by ID."""
        conn = await self.get_by_id(connection_id)
        if conn is not None:
            await self._db_session.delete(conn)
            await self._db_session.flush()

    async def is_referenced_by_accepted_queries(self, connection_id: uuid.UUID) -> bool:
        """Check if connection is referenced by any accepted queries."""
        raw = await self._db_session.execute(
            text("SELECT COUNT(*) FROM accepted_queries WHERE database_connection_id = :id"),
            {"id": str(connection_id)},
        )
        count = raw.scalar()
        return count > 0

    async def is_referenced_by_sessions(self, connection_id: uuid.UUID) -> bool:
        """Check if connection is referenced by any sessions."""
        raw = await self._db_session.execute(
            text("SELECT COUNT(*) FROM sessions WHERE connection_id = :id"),
            {"id": str(connection_id)},
        )
        count = raw.scalar()
        return count > 0

    async def has_schema_entries(self, connection_id: uuid.UUID) -> bool:
        """Check if connection has any schema introspection entries."""
        raw = await self._db_session.execute(
            text("SELECT COUNT(*) FROM connection_schema_entries WHERE connection_id = :id"),
            {"id": str(connection_id)},
        )
        count = raw.scalar()
        return count > 0

    async def get_schema_entries(self, connection_id: uuid.UUID) -> list[ConnectionSchemaEntry]:
        """Get all schema entries for a connection."""
        result = await self._db_session.execute(
            select(ConnectionSchemaEntry)
            .where(ConnectionSchemaEntry.connection_id == connection_id)
            .order_by(ConnectionSchemaEntry.table_name, ConnectionSchemaEntry.column_name)
        )
        return list(result.scalars().all())
