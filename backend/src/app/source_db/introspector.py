"""Schema introspection with TTL caching.

T-100: SchemaIntrospector queries information_schema and builds SchemaContext.
"""

import asyncio
import time

from app.evaluator.schema_context import Column, SchemaContext, Table
from app.source_db.connector import SourceDBConnector


class SchemaIntrospector:
    """Introspect the source database and cache the schema context."""

    def __init__(self, connector: SourceDBConnector, ttl_seconds: int = 300):
        self._connector = connector
        self._ttl_seconds = ttl_seconds
        self._cache: SchemaContext | None = None
        self._cached_at: float = 0.0
        self._lock = asyncio.Lock()

    async def introspect(self, force_refresh: bool = False) -> SchemaContext:
        """Return the current schema context, using cache if valid."""
        if not force_refresh:
            cached = self._get_cached()
            if cached is not None:
                return cached

        async with self._lock:
            # Double-check after acquiring lock
            if not force_refresh:
                cached = self._get_cached()
                if cached is not None:
                    return cached
            schema = await self._fetch_schema()
            self._cache = schema
            self._cached_at = time.monotonic()
            return schema

    async def refresh(self) -> SchemaContext:
        """Force a fresh introspection and update cache."""
        return await self.introspect(force_refresh=True)

    def _get_cached(self) -> SchemaContext | None:
        if self._cache is None:
            return None
        if time.monotonic() - self._cached_at > self._ttl_seconds:
            return None
        return self._cache

    async def _fetch_schema(self) -> SchemaContext:
        async with self._connector.get_connection() as conn:
            tables = await self._fetch_tables(conn)
            columns = await self._fetch_columns(conn)
            pks = await self._fetch_primary_keys(conn)
            fks = await self._fetch_foreign_keys(conn)

        table_map: dict[str, Table] = {}
        for t in tables:
            table_map[t["table_name"]] = Table(
                name=t["table_name"],
                schema_name=t["table_schema"],
                columns=[],
            )

        for c in columns:
            table_name = c["table_name"]
            if table_name not in table_map:
                continue
            col = Column(
                name=c["column_name"],
                type=c["data_type"],
                nullable=c["is_nullable"] == "YES",
                primary_key=False,
            )
            table_map[table_name].columns.append(col)

        # Mark primary keys
        for pk in pks:
            table = table_map.get(pk["table_name"])
            if table is None:
                continue
            for col in table.columns:
                if col.name == pk["column_name"]:
                    col.primary_key = True

        # Attach foreign keys to SchemaContext (store as table metadata)
        schema = SchemaContext(tables=list(table_map.values()))
        return schema

    async def _fetch_tables(self, conn):
        query = """
            SELECT table_name, table_schema
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        return await conn.fetch(query)

    async def _fetch_columns(self, conn):
        query = """
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """
        return await conn.fetch(query)

    async def _fetch_primary_keys(self, conn):
        query = """
            SELECT
                kcu.table_name,
                kcu.column_name,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = 'public'
            ORDER BY kcu.table_name, kcu.ordinal_position
        """
        return await conn.fetch(query)

    async def _fetch_foreign_keys(self, conn):
        query = """
            SELECT
                kcu.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name
             AND tc.table_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
            ORDER BY kcu.table_name, kcu.ordinal_position
        """
        return await conn.fetch(query)
