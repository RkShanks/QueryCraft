"""Tests for ConnectionRepository (T-409, FR-059)."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.database_connection import SourceDatabaseConnection
from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus
from app.repositories.connection_repository import ConnectionRepository


@pytest.fixture
def repository(db_session: AsyncSession) -> ConnectionRepository:
    return ConnectionRepository(db_session)


def _make_connection(**kwargs) -> SourceDatabaseConnection:
    defaults = {
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
    }
    defaults.update(kwargs)
    return SourceDatabaseConnection(**defaults)


class TestConnectionRepositoryCreate:
    """Verify ConnectionRepository.create persists a new connection."""

    @pytest.mark.asyncio
    async def test_create_returns_connection(self, repository: ConnectionRepository, db_session: AsyncSession):
        conn = _make_connection()
        result = await repository.create(conn)
        assert result.id is not None
        assert result.display_name == "Test DB"

    @pytest.mark.asyncio
    async def test_create_persists_to_db(self, repository: ConnectionRepository, db_session: AsyncSession):
        conn = _make_connection(display_name="Persist Test")
        result = await repository.create(conn)
        await db_session.commit()

        fetched = await repository.get_by_id(result.id)
        assert fetched is not None
        assert fetched.display_name == "Persist Test"


class TestConnectionRepositoryGetById:
    """Verify ConnectionRepository.get_by_id returns correct connection."""

    @pytest.mark.asyncio
    async def test_get_existing(self, repository: ConnectionRepository, db_session: AsyncSession):
        conn = _make_connection()
        created = await repository.create(conn)
        await db_session.commit()

        fetched = await repository.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, repository: ConnectionRepository):
        result = await repository.get_by_id(uuid4())
        assert result is None


class TestConnectionRepositoryList:
    """Verify ConnectionRepository.list_all returns connections."""

    @pytest.mark.asyncio
    async def test_list_empty(self, repository: ConnectionRepository):
        results = await repository.list_all()
        assert results == []

    @pytest.mark.asyncio
    async def test_list_returns_all(self, repository: ConnectionRepository, db_session: AsyncSession):
        await repository.create(_make_connection(display_name="DB 1"))
        await repository.create(_make_connection(display_name="DB 2"))
        await db_session.commit()

        results = await repository.list_all()
        assert len(results) == 2


class TestConnectionRepositoryUpdate:
    """Verify ConnectionRepository.update modifies a connection."""

    @pytest.mark.asyncio
    async def test_update_display_name(self, repository: ConnectionRepository, db_session: AsyncSession):
        conn = await repository.create(_make_connection())
        await db_session.commit()

        conn.display_name = "Updated Name"
        result = await repository.update(conn)
        await db_session.commit()

        assert result.display_name == "Updated Name"


class TestConnectionRepositoryDelete:
    """Verify ConnectionRepository.delete removes a connection."""

    @pytest.mark.asyncio
    async def test_delete_existing(self, repository: ConnectionRepository, db_session: AsyncSession):
        conn = await repository.create(_make_connection())
        await db_session.commit()

        await repository.delete(conn.id)
        await db_session.commit()

        fetched = await repository.get_by_id(conn.id)
        assert fetched is None
