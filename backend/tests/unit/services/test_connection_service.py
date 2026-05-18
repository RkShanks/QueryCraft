"""Tests for ConnectionService (T-408, SC-025, SC-029)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from app.core.exceptions import QueryCraftError
from app.db.models.database_connection import SourceDatabaseConnection
from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus
from app.schemas.connection import ConnectionCreate


def _make_create_request(**kwargs) -> ConnectionCreate:
    defaults = {
        "display_name": "Test DB",
        "database_type": DatabaseType.POSTGRESQL,
        "host": "localhost",
        "port": 5432,
        "database_name": "test",
        "username": "user",
        "password": "secret",
    }
    defaults.update(kwargs)
    return ConnectionCreate(**defaults)


def _make_conn(**kwargs) -> SourceDatabaseConnection:
    defaults = {
        "id": uuid4(),
        "display_name": "Test DB",
        "database_type": DatabaseType.POSTGRESQL,
        "host": "localhost",
        "port": 5432,
        "database_name": "test",
        "username": "user",
        "encrypted_password": "encrypted",
        "ssl_mode": "require",
        "lifecycle_state": LifecycleState.ACTIVE,
        "health_status": HealthStatus.UNTESTED,
        "schema_introspection_status": SchemaIntrospectionStatus.NONE,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return SourceDatabaseConnection(**defaults)


class TestConnectionServiceCreate:
    """Verify ConnectionService.create encrypts password and persists."""

    @pytest.mark.asyncio
    async def test_create_encrypts_password(self):
        from app.repositories.connection_repository import ConnectionRepository
        from app.services.connection_service import ConnectionService

        key = Fernet.generate_key().decode()
        mock_repo = MagicMock(spec=ConnectionRepository)
        conn = _make_conn()
        mock_repo.create = AsyncMock(return_value=conn)

        service = ConnectionService(mock_repo, key)
        req = _make_create_request()
        result = await service.create(req)

        call_args = mock_repo.create.call_args
        conn_arg = call_args[0][0]
        assert conn_arg.encrypted_password != "secret"
        assert conn_arg.encrypted_password != req.password
        assert result.display_name == "Test DB"

    @pytest.mark.asyncio
    async def test_create_auto_introspect_health_check_passes(self):
        """Create triggers health check and introspection on success."""
        from app.repositories.connection_repository import ConnectionRepository
        from app.services.connection_service import ConnectionService

        key = Fernet.generate_key().decode()
        mock_repo = MagicMock(spec=ConnectionRepository)

        conn_id = uuid4()
        created_conn = _make_conn(
            id=conn_id,
            health_status=HealthStatus.UNTESTED,
            schema_introspection_status=SchemaIntrospectionStatus.NONE,
        )

        def capture_create(conn):
            conn.id = conn_id
            conn.created_at = datetime.now(UTC)
            conn.updated_at = datetime.now(UTC)
            return conn

        mock_repo.create = AsyncMock(side_effect=capture_create)
        mock_repo.update = AsyncMock(return_value=created_conn)

        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.add_all = MagicMock()

        service = ConnectionService(mock_repo, key, get_db_session=lambda: mock_session)

        mock_adapter = AsyncMock()
        mock_adapter.health_check = AsyncMock(return_value=True)
        mock_adapter.close = AsyncMock()
        mock_adapter.execute = AsyncMock(return_value=MagicMock(columns=[], rows=[]))
        service._build_adapter = MagicMock(return_value=mock_adapter)

        req = _make_create_request()
        result = await service.create(req)

        assert result.health_status == HealthStatus.HEALTHY
        assert result.schema_introspection_status == SchemaIntrospectionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_create_auto_introspect_health_check_fails(self):
        """Create marks status as UNHEALTHY/FAILED when health check fails."""
        from app.repositories.connection_repository import ConnectionRepository
        from app.services.connection_service import ConnectionService

        key = Fernet.generate_key().decode()
        mock_repo = MagicMock(spec=ConnectionRepository)

        conn_id = uuid4()
        created_conn = _make_conn(
            id=conn_id,
            health_status=HealthStatus.UNTESTED,
            schema_introspection_status=SchemaIntrospectionStatus.NONE,
        )

        def capture_create(conn):
            conn.id = conn_id
            conn.created_at = datetime.now(UTC)
            conn.updated_at = datetime.now(UTC)
            return conn

        mock_repo.create = AsyncMock(side_effect=capture_create)
        mock_repo.update = AsyncMock(return_value=created_conn)

        service = ConnectionService(mock_repo, key, get_db_session=lambda: MagicMock())

        mock_adapter = AsyncMock()
        mock_adapter.health_check = AsyncMock(return_value=False)
        mock_adapter.close = AsyncMock()
        service._build_adapter = MagicMock(return_value=mock_adapter)

        req = _make_create_request()
        result = await service.create(req)

        assert result.health_status == HealthStatus.UNHEALTHY
        assert result.schema_introspection_status == SchemaIntrospectionStatus.FAILED

    @pytest.mark.asyncio
    async def test_create_auto_introspect_exception(self):
        """Create marks status as FAILED when introspection raises."""
        from app.repositories.connection_repository import ConnectionRepository
        from app.services.connection_service import ConnectionService

        key = Fernet.generate_key().decode()
        mock_repo = MagicMock(spec=ConnectionRepository)

        conn_id = uuid4()
        created_conn = _make_conn(
            id=conn_id,
            health_status=HealthStatus.UNTESTED,
            schema_introspection_status=SchemaIntrospectionStatus.NONE,
        )

        def capture_create(conn):
            conn.id = conn_id
            conn.created_at = datetime.now(UTC)
            conn.updated_at = datetime.now(UTC)
            return conn

        mock_repo.create = AsyncMock(side_effect=capture_create)
        mock_repo.update = AsyncMock(return_value=created_conn)

        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.add_all = MagicMock()

        service = ConnectionService(mock_repo, key, get_db_session=lambda: mock_session)

        mock_adapter = AsyncMock()
        mock_adapter.health_check = AsyncMock(return_value=True)
        mock_adapter.close = AsyncMock()
        mock_adapter.execute = AsyncMock(side_effect=ConnectionError("db down"))
        service._build_adapter = MagicMock(return_value=mock_adapter)

        req = _make_create_request()
        result = await service.create(req)

        assert result.health_status == HealthStatus.HEALTHY
        assert result.schema_introspection_status == SchemaIntrospectionStatus.FAILED


class TestConnectionServiceLifecycle:
    """Verify lifecycle transitions."""

    @pytest.mark.asyncio
    async def test_disable_connection(self):
        from app.repositories.connection_repository import ConnectionRepository
        from app.services.connection_service import ConnectionService

        key = Fernet.generate_key().decode()
        mock_repo = MagicMock(spec=ConnectionRepository)
        conn = _make_conn(lifecycle_state=LifecycleState.ACTIVE)
        mock_repo.get_by_id = AsyncMock(return_value=conn)
        mock_repo.update = AsyncMock(return_value=conn)

        service = ConnectionService(mock_repo, key)
        result = await service.disable(conn.id)

        assert result.lifecycle_state == LifecycleState.DISABLED

    @pytest.mark.asyncio
    async def test_enable_connection(self):
        from app.repositories.connection_repository import ConnectionRepository
        from app.services.connection_service import ConnectionService

        key = Fernet.generate_key().decode()
        mock_repo = MagicMock(spec=ConnectionRepository)
        conn = _make_conn(lifecycle_state=LifecycleState.DISABLED)
        mock_repo.get_by_id = AsyncMock(return_value=conn)
        mock_repo.update = AsyncMock(return_value=conn)

        service = ConnectionService(mock_repo, key)
        result = await service.enable(conn.id)

        assert result.lifecycle_state == LifecycleState.ACTIVE


class TestConnectionServiceHardDeleteGuard:
    """Verify hard-delete is blocked when referenced."""

    @pytest.mark.asyncio
    async def test_delete_blocked_by_accepted_queries(self):
        from app.repositories.connection_repository import ConnectionRepository
        from app.services.connection_service import ConnectionReferencedError, ConnectionService

        key = Fernet.generate_key().decode()
        mock_repo = MagicMock(spec=ConnectionRepository)
        conn_id = uuid4()
        mock_repo.get_by_id = AsyncMock(return_value=_make_conn(id=conn_id))
        mock_repo.is_referenced_by_accepted_queries = AsyncMock(return_value=True)
        mock_repo.is_referenced_by_sessions = AsyncMock(return_value=False)
        mock_repo.has_schema_entries = AsyncMock(return_value=False)

        service = ConnectionService(mock_repo, key)

        with pytest.raises(ConnectionReferencedError):
            await service.hard_delete(conn_id)

    @pytest.mark.asyncio
    async def test_delete_blocked_by_sessions(self):
        from app.repositories.connection_repository import ConnectionRepository
        from app.services.connection_service import ConnectionReferencedError, ConnectionService

        key = Fernet.generate_key().decode()
        mock_repo = MagicMock(spec=ConnectionRepository)
        conn_id = uuid4()
        mock_repo.get_by_id = AsyncMock(return_value=_make_conn(id=conn_id))
        mock_repo.is_referenced_by_accepted_queries = AsyncMock(return_value=False)
        mock_repo.is_referenced_by_sessions = AsyncMock(return_value=True)
        mock_repo.has_schema_entries = AsyncMock(return_value=False)

        service = ConnectionService(mock_repo, key)

        with pytest.raises(ConnectionReferencedError):
            await service.hard_delete(conn_id)

    @pytest.mark.asyncio
    async def test_delete_blocked_by_schema_entries(self):
        from app.repositories.connection_repository import ConnectionRepository
        from app.services.connection_service import ConnectionReferencedError, ConnectionService

        key = Fernet.generate_key().decode()
        mock_repo = MagicMock(spec=ConnectionRepository)
        conn_id = uuid4()
        mock_repo.get_by_id = AsyncMock(return_value=_make_conn(id=conn_id))
        mock_repo.is_referenced_by_accepted_queries = AsyncMock(return_value=False)
        mock_repo.is_referenced_by_sessions = AsyncMock(return_value=False)
        mock_repo.has_schema_entries = AsyncMock(return_value=True)

        service = ConnectionService(mock_repo, key)

        with pytest.raises(ConnectionReferencedError):
            await service.hard_delete(conn_id)

    @pytest.mark.asyncio
    async def test_delete_succeeds_when_unreferenced(self):
        from app.repositories.connection_repository import ConnectionRepository
        from app.services.connection_service import ConnectionService

        key = Fernet.generate_key().decode()
        mock_repo = MagicMock(spec=ConnectionRepository)
        conn_id = uuid4()
        mock_repo.get_by_id = AsyncMock(return_value=_make_conn(id=conn_id))
        mock_repo.is_referenced_by_accepted_queries = AsyncMock(return_value=False)
        mock_repo.is_referenced_by_sessions = AsyncMock(return_value=False)
        mock_repo.has_schema_entries = AsyncMock(return_value=False)
        mock_repo.delete = AsyncMock()

        service = ConnectionService(mock_repo, key)
        await service.hard_delete(conn_id)

        mock_repo.delete.assert_called_once_with(conn_id)


class TestConnectionServiceRefreshSchema:
    """Verify refresh_schema updates status correctly."""

    @pytest.mark.asyncio
    async def test_refresh_schema_success(self):
        from app.repositories.connection_repository import ConnectionRepository
        from app.services.connection_service import ConnectionService

        key = Fernet.generate_key().decode()
        provider = Fernet(key)
        encrypted_pw = provider.encrypt(b"secret").decode()

        mock_repo = MagicMock(spec=ConnectionRepository)
        conn = _make_conn(
            schema_introspection_status=SchemaIntrospectionStatus.NONE,
            health_status=HealthStatus.HEALTHY,
            encrypted_password=encrypted_pw,
        )
        mock_repo.get_by_id = AsyncMock(return_value=conn)
        mock_repo.update = AsyncMock(return_value=conn)

        service = ConnectionService(mock_repo, key)

        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.add_all = MagicMock()
        service._get_db_session = lambda: mock_session

        mock_adapter = AsyncMock()
        mock_adapter.execute = AsyncMock(return_value=MagicMock(columns=[], rows=[]))
        mock_adapter.close = AsyncMock()
        service._build_adapter = MagicMock(return_value=mock_adapter)

        result = await service.refresh_schema(conn.id)

        assert result["tables_count"] == 0
        assert conn.schema_introspection_status == SchemaIntrospectionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_refresh_schema_failure(self):
        from app.repositories.connection_repository import ConnectionRepository
        from app.services.connection_service import ConnectionService

        key = Fernet.generate_key().decode()
        provider = Fernet(key)
        encrypted_pw = provider.encrypt(b"secret").decode()

        mock_repo = MagicMock(spec=ConnectionRepository)
        conn = _make_conn(
            schema_introspection_status=SchemaIntrospectionStatus.SUCCESS,
            health_status=HealthStatus.HEALTHY,
            encrypted_password=encrypted_pw,
        )
        mock_repo.get_by_id = AsyncMock(return_value=conn)
        mock_repo.update = AsyncMock(return_value=conn)

        service = ConnectionService(mock_repo, key)

        mock_session = MagicMock()
        service._get_db_session = lambda: mock_session

        mock_adapter = AsyncMock()
        mock_adapter.execute = AsyncMock(side_effect=ConnectionError("db down"))
        mock_adapter.close = AsyncMock()
        service._build_adapter = MagicMock(return_value=mock_adapter)

        with pytest.raises(QueryCraftError):
            await service.refresh_schema(conn.id)

        assert conn.schema_introspection_status == SchemaIntrospectionStatus.FAILED


class TestConnectionServiceGetSchemaSummary:
    """Verify get_schema_summary returns grouped schema data."""

    @pytest.mark.asyncio
    async def test_get_schema_summary(self):
        from app.repositories.connection_repository import ConnectionRepository
        from app.services.connection_service import ConnectionService

        key = Fernet.generate_key().decode()
        mock_repo = MagicMock(spec=ConnectionRepository)
        conn_id = uuid4()
        mock_repo.get_by_id = AsyncMock(return_value=_make_conn(id=conn_id))
        mock_repo.get_schema_entries = AsyncMock(return_value=[])

        service = ConnectionService(mock_repo, key)
        result = await service.get_schema_summary(conn_id)

        assert result["connection_id"] == conn_id
        assert result["tables"] == []
