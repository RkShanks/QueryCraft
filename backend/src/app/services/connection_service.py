"""Connection service for source database connection management.

FR-059, FR-060, FR-061, FR-063, FR-064, FR-089, FR-090.
"""

import contextlib
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.core.credential_provider import FernetCredentialProvider
from app.core.exceptions import QueryCraftError
from app.db.models.database_connection import SourceDatabaseConnection
from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.connection import (
    ConnectionCreate,
    ConnectionResponse,
    ConnectionTestResult,
    ConnectionUpdate,
    UserConnectionListResponse,
    UserConnectionResponse,
)


class ConnectionReferencedError(QueryCraftError):
    """Raised when attempting to hard-delete a connection that is still referenced."""

    def __init__(self) -> None:
        super().__init__(
            "Connection is referenced by query attempts or sessions",
            message_key="error.connection_referenced_delete_blocked",
        )


class ConnectionNotFoundError(QueryCraftError):
    """Raised when a connection ID is not found."""

    def __init__(self, connection_id: uuid.UUID) -> None:
        super().__init__(
            f"Connection {connection_id} not found",
            message_key="error.connection_not_found",
        )
        self.connection_id = connection_id


class ConnectionService:
    """Business logic for source database connection lifecycle."""

    def __init__(
        self,
        repository: ConnectionRepository,
        credential_key: str,
        get_db_session: Callable | None = None,
    ) -> None:
        self._repo = repository
        self._credential_provider = FernetCredentialProvider(credential_key)
        self._get_db_session = get_db_session or (lambda: None)

    async def create(self, req: ConnectionCreate) -> ConnectionResponse:
        """Create a new source database connection.

        After persisting, runs auto-introspect pipeline: health check → introspect.
        Statuses are updated accordingly (FR-093).
        """
        encrypted_password = self._credential_provider.encrypt(req.password)

        conn = SourceDatabaseConnection(
            display_name=req.display_name,
            database_type=req.database_type,
            host=req.host,
            port=req.port,
            database_name=req.database_name,
            username=req.username,
            encrypted_password=encrypted_password,
            ssl_mode=req.ssl_mode,
            lifecycle_state=LifecycleState.ACTIVE,
            health_status=HealthStatus.UNTESTED,
            schema_introspection_status=SchemaIntrospectionStatus.NONE,
        )

        created = await self._repo.create(conn)

        # Auto-introspect pipeline: health check → introspect (FR-093)
        await self._auto_introspect_on_create(created)

        return ConnectionResponse.model_validate(created)

    async def _auto_introspect_on_create(self, conn: SourceDatabaseConnection) -> None:
        """Run health check and introspection after first save.

        Updates connection health_status and schema_introspection_status.
        Errors are caught and statuses marked as FAILED — connection is not rolled back.
        """
        try:
            adapter = self._build_adapter(conn)
            healthy = await adapter.health_check()
            await adapter.close()

            if healthy:
                conn.health_status = HealthStatus.HEALTHY
                conn.last_health_check_at = datetime.now(UTC)
                conn.health_error_category = None
            else:
                conn.health_status = HealthStatus.UNHEALTHY
                conn.last_health_check_at = datetime.now(UTC)
                conn.health_error_category = "unknown"
                conn.schema_introspection_status = SchemaIntrospectionStatus.FAILED
                await self._repo.update(conn)
                return

            await self._repo.update(conn)

            # Run introspection if healthy
            db_session = self._get_db_session()
            if db_session is None:
                conn.schema_introspection_status = SchemaIntrospectionStatus.FAILED
                await self._repo.update(conn)
                return

            from app.source_db.schema_introspector import SchemaIntrospector

            introspector = SchemaIntrospector(
                adapter=self._build_adapter(conn),
                database_type=conn.database_type,
                db_session=db_session,
                connection_id=conn.id,
            )

            result = await introspector.introspect()
            conn.schema_introspection_status = SchemaIntrospectionStatus.SUCCESS
            conn.schema_last_refreshed_at = result["refreshed_at"]
            await self._repo.update(conn)
        except Exception:
            conn.schema_introspection_status = SchemaIntrospectionStatus.FAILED
            with contextlib.suppress(Exception):
                await self._repo.update(conn)

    async def get_by_id(self, connection_id: uuid.UUID) -> ConnectionResponse:
        """Get a connection by ID."""
        conn = await self._repo.get_by_id(connection_id)
        if conn is None:
            raise ConnectionNotFoundError(connection_id)
        return ConnectionResponse.model_validate(conn)

    async def list_all(self) -> list[ConnectionResponse]:
        """List all connections."""
        connections = await self._repo.list_all()
        return [ConnectionResponse.model_validate(c) for c in connections]

    async def list_user_available(self) -> UserConnectionListResponse:
        """List connections available for user selection (T-428, FR-077).

        Returns only active + healthy + successfully introspected connections
        with minimal payload (id, display_name, database_type).
        """
        connections = await self._repo.list_user_available()
        items = [
            UserConnectionResponse(
                id=c.id,
                display_name=c.display_name,
                database_type=c.database_type,
            )
            for c in connections
        ]
        return UserConnectionListResponse(connections=items)

    async def update(self, connection_id: uuid.UUID, req: ConnectionUpdate) -> ConnectionResponse:
        """Update an existing connection."""
        conn = await self._repo.get_by_id(connection_id)
        if conn is None:
            raise ConnectionNotFoundError(connection_id)

        if req.display_name is not None:
            conn.display_name = req.display_name
        if req.database_type is not None:
            conn.database_type = req.database_type
        if req.host is not None:
            conn.host = req.host
        if req.port is not None:
            conn.port = req.port
        if req.database_name is not None:
            conn.database_name = req.database_name
        if req.username is not None:
            conn.username = req.username
        if req.password is not None:
            conn.encrypted_password = self._credential_provider.encrypt(req.password)
        if req.ssl_mode is not None:
            conn.ssl_mode = req.ssl_mode

        updated = await self._repo.update(conn)
        return ConnectionResponse.model_validate(updated)

    async def disable(self, connection_id: uuid.UUID) -> ConnectionResponse:
        """Disable an active connection."""
        conn = await self._repo.get_by_id(connection_id)
        if conn is None:
            raise ConnectionNotFoundError(connection_id)

        if conn.lifecycle_state == LifecycleState.DISABLED:
            raise QueryCraftError(
                "Connection is already disabled",
                message_key="error.connection_already_disabled",
            )

        conn.lifecycle_state = LifecycleState.DISABLED
        updated = await self._repo.update(conn)
        return ConnectionResponse.model_validate(updated)

    async def enable(self, connection_id: uuid.UUID) -> ConnectionResponse:
        """Re-enable a disabled connection."""
        conn = await self._repo.get_by_id(connection_id)
        if conn is None:
            raise ConnectionNotFoundError(connection_id)

        if conn.lifecycle_state == LifecycleState.ACTIVE:
            raise QueryCraftError(
                "Connection is already active",
                message_key="error.connection_already_active",
            )

        conn.lifecycle_state = LifecycleState.ACTIVE
        updated = await self._repo.update(conn)
        return ConnectionResponse.model_validate(updated)

    async def test_connection(self, connection_id: uuid.UUID) -> ConnectionTestResult:
        """Test a connection's health via SELECT 1."""
        conn = await self._repo.get_by_id(connection_id)
        if conn is None:
            raise ConnectionNotFoundError(connection_id)

        start = time.monotonic()
        try:
            decrypted_password = self._credential_provider.decrypt(conn.encrypted_password)
            # Build connection URL based on database type
            if conn.database_type == DatabaseType.POSTGRESQL:
                import asyncpg

                db_url = (
                    f"postgresql://{conn.username}:{decrypted_password}@{conn.host}:{conn.port}/{conn.database_name}"
                )
                if conn.ssl_mode != "disable":
                    db_url += f"?ssl={conn.ssl_mode}"

                conn_pg = await asyncpg.connect(db_url)
                await conn_pg.execute("SELECT 1")
                await conn_pg.close()
            else:
                # For MySQL/MSSQL, we'd use the appropriate driver
                # For now, mark as untested since drivers may not be installed
                raise NotImplementedError(f"Health check not implemented for {conn.database_type.value}")

            latency_ms = (time.monotonic() - start) * 1000

            conn.health_status = HealthStatus.HEALTHY
            conn.last_health_check_at = datetime.now(UTC)
            conn.health_error_category = None
            await self._repo.update(conn)

            return ConnectionTestResult(
                status="healthy",
                latency_ms=round(latency_ms, 2),
                tested_at=datetime.now(UTC),
            )
        except NotImplementedError:
            latency_ms = (time.monotonic() - start) * 1000
            return ConnectionTestResult(
                status="unhealthy",
                latency_ms=round(latency_ms, 2),
                error_category="not_implemented",
                message_key="error.connection_unhealthy",
                tested_at=datetime.now(UTC),
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            error_category = self._classify_error(str(e))

            conn.health_status = HealthStatus.UNHEALTHY
            conn.last_health_check_at = datetime.now(UTC)
            conn.health_error_category = error_category
            await self._repo.update(conn)

            return ConnectionTestResult(
                status="unhealthy",
                latency_ms=round(latency_ms, 2),
                error_category=error_category,
                message_key=f"error.connection_{error_category}",
                tested_at=datetime.now(UTC),
            )

    async def hard_delete(self, connection_id: uuid.UUID) -> None:
        """Hard-delete a connection only if unreferenced.

        Blocked if referenced by accepted_queries, sessions, or schema entries.
        """
        conn = await self._repo.get_by_id(connection_id)
        if conn is None:
            raise ConnectionNotFoundError(connection_id)

        if await self._repo.is_referenced_by_accepted_queries(connection_id):
            raise ConnectionReferencedError()

        if await self._repo.is_referenced_by_sessions(connection_id):
            raise ConnectionReferencedError()

        if await self._repo.has_schema_entries(connection_id):
            raise ConnectionReferencedError()

        await self._repo.delete(connection_id)

    @staticmethod
    def _classify_error(error_msg: str) -> str:
        """Classify a connection error into a category."""
        error_lower = error_msg.lower()
        if "authentication" in error_lower or "password" in error_lower or "role" in error_lower:
            return "auth_failed"
        if "connection refused" in error_lower or "network" in error_lower or "unreachable" in error_lower:
            return "network_unreachable"
        if "database" in error_lower and "not exist" in error_lower:
            return "db_not_found"
        if "timeout" in error_lower:
            return "timeout"
        return "unknown"

    async def refresh_schema(self, connection_id: uuid.UUID) -> dict[str, Any]:
        """Run schema introspection for a connection.

        Updates schema_introspection_status and schema_last_refreshed_at.
        """
        from app.source_db.schema_introspector import SchemaIntrospectionError, SchemaIntrospector

        conn = await self._repo.get_by_id(connection_id)
        if conn is None:
            raise ConnectionNotFoundError(connection_id)

        adapter = self._build_adapter(conn)
        db_session = self._get_db_session()

        introspector = SchemaIntrospector(
            adapter=adapter,
            database_type=conn.database_type,
            db_session=db_session,
            connection_id=connection_id,
        )

        try:
            result = await introspector.introspect()
            conn.schema_introspection_status = SchemaIntrospectionStatus.SUCCESS
            conn.schema_last_refreshed_at = result["refreshed_at"]
            await self._repo.update(conn)
            return result
        except SchemaIntrospectionError as e:
            conn.schema_introspection_status = SchemaIntrospectionStatus.FAILED
            await self._repo.update(conn)
            raise QueryCraftError(
                f"Schema introspection failed: {e.detail}",
                message_key="error.introspection_failed",
                detail=e.detail,
            ) from e
        finally:
            await adapter.close()

    async def get_schema_summary(self, connection_id: uuid.UUID) -> dict[str, Any]:
        """Get the introspected schema summary for a connection."""
        conn = await self._repo.get_by_id(connection_id)
        if conn is None:
            raise ConnectionNotFoundError(connection_id)

        entries = await self._repo.get_schema_entries(connection_id)

        tables_map: dict[str, dict] = {}
        for entry in entries:
            tname = entry.table_name
            if tname not in tables_map:
                tables_map[tname] = {
                    "table_name": tname,
                    "column_count": 0,
                    "columns": [],
                }
            col_info = {
                "column_name": entry.column_name,
                "data_type": entry.column_data_type,
                "is_primary_key": entry.is_primary_key,
                "foreign_key": None,
            }
            if entry.foreign_key_table:
                col_info["foreign_key"] = {
                    "table": entry.foreign_key_table,
                    "column": entry.foreign_key_column,
                }
            tables_map[tname]["columns"].append(col_info)
            tables_map[tname]["column_count"] += 1

        latest_introspected_at = max((e.introspected_at for e in entries), default=None)

        return {
            "connection_id": connection_id,
            "tables": list(tables_map.values()),
            "introspected_at": latest_introspected_at,
        }

    def _build_adapter(self, conn: SourceDatabaseConnection) -> Any:
        """Build a SourceDBAdapter for the given connection."""
        from app.source_db.adapters import MSSQLAdapter, MySQLAdapter, PostgresAdapter

        adapter_map = {
            DatabaseType.POSTGRESQL: PostgresAdapter,
            DatabaseType.MYSQL: MySQLAdapter,
            DatabaseType.MSSQL: MSSQLAdapter,
        }
        adapter_cls = adapter_map.get(conn.database_type)
        if adapter_cls is None:
            raise QueryCraftError(f"Unsupported database type: {conn.database_type.value}")

        return adapter_cls(
            host=conn.host,
            port=conn.port,
            database=conn.database_name,
            username=conn.username,
            encrypted_password=conn.encrypted_password,
            ssl_mode=conn.ssl_mode,
            credential_provider=self._credential_provider,
        )
