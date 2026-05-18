"""Tests for ConnectionService (T-408, SC-025, SC-029)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

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
