"""Schema introspection with per-dialect information_schema queries (FR-065, FR-066, ADR-11).

Full-replace refresh: on each introspection, all existing entries for the
connection are deleted and re-inserted.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.connection_schema import ConnectionSchemaEntry
from app.db.models.enums import DatabaseType
from app.source_db.adapters import SourceDBAdapter


class SchemaIntrospectionError(Exception):
    """Raised when schema introspection fails."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Schema introspection failed: {detail}")
        self.detail = detail


class SchemaIntrospector:
    """Per-dialect schema introspection strategy.

    Queries information_schema (or dialect equivalent) for tables, columns,
    primary keys, and foreign keys. Performs full-replace refresh.
    """

    def __init__(
        self,
        adapter: SourceDBAdapter,
        database_type: DatabaseType,
        db_session: AsyncSession,
        connection_id: uuid.UUID,
    ) -> None:
        self._adapter = adapter
        self._database_type = database_type
        self._db_session = db_session
        self._connection_id = connection_id

    async def introspect(self) -> dict[str, Any]:
        """Run full-replace schema introspection.

        Returns:
            Dict with tables_count, columns_count, refreshed_at.

        Raises:
            SchemaIntrospectionError: on any failure.
        """
        try:
            tables, columns = await self._fetch_schema(self._adapter)
            pks = await self._fetch_primary_keys(self._adapter)
            fks = await self._fetch_foreign_keys(self._adapter)
        except Exception as e:
            raise SchemaIntrospectionError(str(e)) from e

        pk_set = {(row["table_name"], row["column_name"]) for row in pks}
        fk_map = {(row["table_name"], row["column_name"]): row for row in fks}

        entries = []
        for col in columns:
            table_name = col["table_name"]
            column_name = col["column_name"]
            is_pk = (table_name, column_name) in pk_set
            fk_info = fk_map.get((table_name, column_name))

            entry = ConnectionSchemaEntry(
                connection_id=self._connection_id,
                table_name=table_name,
                column_name=column_name,
                column_data_type=col["data_type"],
                is_primary_key=is_pk,
                foreign_key_table=fk_info.get("foreign_table_name") if fk_info else None,
                foreign_key_column=fk_info.get("foreign_column_name") if fk_info else None,
            )
            entries.append(entry)

        await self._full_replace(entries)

        refreshed_at = datetime.now(UTC)
        return {
            "tables_count": len(set(c["table_name"] for c in columns)),
            "columns_count": len(columns),
            "refreshed_at": refreshed_at,
        }

    async def _fetch_schema(self, adapter: SourceDBAdapter) -> tuple[list[dict], list[dict]]:
        """Fetch tables and columns from information_schema."""
        tables_result = await adapter.execute(self._tables_query())
        columns_result = await adapter.execute(self._columns_query())

        tables = [dict(zip(tables_result.columns, row, strict=False)) for row in tables_result.rows]
        columns = [dict(zip(columns_result.columns, row, strict=False)) for row in columns_result.rows]
        return tables, columns

    async def _fetch_primary_keys(self, adapter: SourceDBAdapter) -> list[dict]:
        """Fetch primary key columns."""
        result = await adapter.execute(self._primary_keys_query())
        return [dict(zip(result.columns, row, strict=False)) for row in result.rows]

    async def _fetch_foreign_keys(self, adapter: SourceDBAdapter) -> list[dict]:
        """Fetch foreign key columns."""
        result = await adapter.execute(self._foreign_keys_query())
        return [dict(zip(result.columns, row, strict=False)) for row in result.rows]

    async def _full_replace(self, entries: list[ConnectionSchemaEntry]) -> None:
        """Delete all existing entries and insert new ones."""
        await self._db_session.execute(
            delete(ConnectionSchemaEntry).where(ConnectionSchemaEntry.connection_id == self._connection_id)
        )
        if entries:
            self._db_session.add_all(entries)
        await self._db_session.flush()

    def _tables_query(self) -> str:
        """Return dialect-specific tables query."""
        if self._database_type == DatabaseType.MSSQL:
            return """
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """
        if self._database_type == DatabaseType.MYSQL:
            return """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema = DATABASE()
                ORDER BY table_name
            """
        return """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_schema = 'public'
            ORDER BY table_name
        """

    def _columns_query(self) -> str:
        """Return dialect-specific columns query."""
        if self._database_type == DatabaseType.MSSQL:
            return """
                SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                ORDER BY TABLE_NAME, ORDINAL_POSITION
            """
        if self._database_type == DatabaseType.MYSQL:
            return """
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                ORDER BY table_name, ordinal_position
            """
        return """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """

    def _primary_keys_query(self) -> str:
        """Return dialect-specific primary keys query."""
        if self._database_type == DatabaseType.MSSQL:
            return """
                SELECT
                    KCU.TABLE_NAME,
                    KCU.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS TC
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE KCU
                    ON TC.CONSTRAINT_NAME = KCU.CONSTRAINT_NAME
                WHERE TC.CONSTRAINT_TYPE = 'PRIMARY KEY'
                ORDER BY KCU.TABLE_NAME, KCU.ORDINAL_POSITION
            """
        if self._database_type == DatabaseType.MYSQL:
            return """
                SELECT
                    kcu.table_name,
                    kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = DATABASE()
                ORDER BY kcu.table_name, kcu.ordinal_position
            """
        return """
            SELECT
                kcu.table_name,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = 'public'
            ORDER BY kcu.table_name, kcu.ordinal_position
        """

    def _foreign_keys_query(self) -> str:
        """Return dialect-specific foreign keys query."""
        if self._database_type == DatabaseType.MSSQL:
            return """
                SELECT
                    KCU.TABLE_NAME,
                    KCU.COLUMN_NAME,
                    CCU.TABLE_NAME AS foreign_table_name,
                    CCU.COLUMN_NAME AS foreign_column_name
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS TC
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE KCU
                    ON TC.CONSTRAINT_NAME = KCU.CONSTRAINT_NAME
                JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE CCU
                    ON TC.CONSTRAINT_NAME = CCU.CONSTRAINT_NAME
                WHERE TC.CONSTRAINT_TYPE = 'FOREIGN KEY'
                ORDER BY KCU.TABLE_NAME, KCU.ORDINAL_POSITION
            """
        if self._database_type == DatabaseType.MYSQL:
            return """
                SELECT
                    kcu.table_name,
                    kcu.column_name,
                    kcu.referenced_table_name AS foreign_table_name,
                    kcu.referenced_column_name AS foreign_column_name
                FROM information_schema.key_column_usage kcu
                WHERE kcu.referenced_table_name IS NOT NULL
                  AND kcu.table_schema = DATABASE()
                ORDER BY kcu.table_name, kcu.ordinal_position
            """
        return """
            SELECT
                kcu.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
            ORDER BY kcu.table_name, kcu.ordinal_position
        """
