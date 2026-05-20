"""Tests for ConnectionRepository (T-409, FR-059)."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.database_connection import SourceDatabaseConnection
from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus
from app.repositories.connection_repository import ConnectionRepository


@pytest.fixture(autouse=True)
async def _clean_connections_table(async_engine_fixture):
    """Truncate source_database_connections before each test for isolation."""
    async with async_engine_fixture.connect() as conn:
        await conn.execute(text("DELETE FROM connection_schema_entries"))
        await conn.execute(text("DELETE FROM accepted_queries WHERE database_connection_id IS NOT NULL"))
        await conn.execute(text("DELETE FROM sessions WHERE connection_id IS NOT NULL"))
        await conn.execute(text("DELETE FROM source_database_connections"))
        await conn.commit()


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


class TestSourceConnectionEnumPersistence:
    """Verify all four enum columns persist and load as DB string values (T-454-hardening)."""

    @pytest.mark.asyncio
    async def test_persist_database_type_all_values(self, repository: ConnectionRepository, db_session: AsyncSession):
        for db_type in DatabaseType:
            conn = _make_connection(display_name=f"Enum {db_type.value}", database_type=db_type)
            created = await repository.create(conn)
            await db_session.commit()

            fetched = await repository.get_by_id(created.id)
            assert fetched is not None
            assert fetched.database_type == db_type
            assert fetched.database_type.value == db_type.value

    @pytest.mark.asyncio
    async def test_persist_lifecycle_state_all_values(self, repository: ConnectionRepository, db_session: AsyncSession):
        for state in LifecycleState:
            conn = _make_connection(display_name=f"Lifecycle {state.value}", lifecycle_state=state)
            created = await repository.create(conn)
            await db_session.commit()

            fetched = await repository.get_by_id(created.id)
            assert fetched is not None
            assert fetched.lifecycle_state == state
            assert fetched.lifecycle_state.value == state.value

    @pytest.mark.asyncio
    async def test_persist_health_status_all_values(self, repository: ConnectionRepository, db_session: AsyncSession):
        for status in HealthStatus:
            conn = _make_connection(display_name=f"Health {status.value}", health_status=status)
            created = await repository.create(conn)
            await db_session.commit()

            fetched = await repository.get_by_id(created.id)
            assert fetched is not None
            assert fetched.health_status == status
            assert fetched.health_status.value == status.value

    @pytest.mark.asyncio
    async def test_persist_schema_introspection_status_all_values(
        self, repository: ConnectionRepository, db_session: AsyncSession
    ):
        for status in SchemaIntrospectionStatus:
            conn = _make_connection(
                display_name=f"Schema {status.value}",
                schema_introspection_status=status,
            )
            created = await repository.create(conn)
            await db_session.commit()

            fetched = await repository.get_by_id(created.id)
            assert fetched is not None
            assert fetched.schema_introspection_status == status
            assert fetched.schema_introspection_status.value == status.value

    @pytest.mark.asyncio
    async def test_db_string_values_deserialize_correctly(
        self, repository: ConnectionRepository, db_session: AsyncSession
    ):
        """Verify existing DB string values like 'postgresql', 'active', 'healthy', 'success'
        deserialize to correct enum members."""
        conn = _make_connection(
            display_name="String Values Test",
            database_type=DatabaseType.POSTGRESQL,
            lifecycle_state=LifecycleState.ACTIVE,
            health_status=HealthStatus.HEALTHY,
            schema_introspection_status=SchemaIntrospectionStatus.SUCCESS,
        )
        created = await repository.create(conn)
        await db_session.commit()

        fetched = await repository.get_by_id(created.id)
        assert fetched.database_type.value == "postgresql"
        assert fetched.lifecycle_state.value == "active"
        assert fetched.health_status.value == "healthy"
        assert fetched.schema_introspection_status.value == "success"

    @pytest.mark.asyncio
    async def test_list_does_not_reference_missing_pg_enum_types(
        self, repository: ConnectionRepository, db_session: AsyncSession
    ):
        """Verify list path works without referencing missing PostgreSQL enum types."""
        await repository.create(_make_connection(display_name="List Test 1"))
        await repository.create(_make_connection(display_name="List Test 2"))
        await db_session.commit()

        results = await repository.list_all()
        assert len(results) == 2
        for conn in results:
            assert isinstance(conn.database_type, DatabaseType)
            assert isinstance(conn.lifecycle_state, LifecycleState)
            assert isinstance(conn.health_status, HealthStatus)
            assert isinstance(conn.schema_introspection_status, SchemaIntrospectionStatus)
