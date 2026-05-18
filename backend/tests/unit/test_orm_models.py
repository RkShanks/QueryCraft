"""Tests for ORM model instantiation and metadata (T-042, T-401).

Asserts User, AcceptedQuery, SourceDatabaseConnection, AppConfig models can be instantiated,
have correct table names, and column types match data-model.md.
"""

from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.models.accepted_query import AcceptedQuery
from app.db.models.app_config import AppConfig
from app.db.models.database_connection import SourceDatabaseConnection
from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus
from app.db.models.user import User


class TestUserModel:
    """User ORM model metadata and instantiation."""

    def test_table_name(self):
        assert User.__tablename__ == "users"

    def test_can_instantiate(self):
        user = User(
            id=uuid4(),
            username="admin",
            display_name="Administrator",
            password_hash="$argon2id$...",
            role="admin",
        )
        assert user.username == "admin"

    def test_id_column_type(self):
        assert isinstance(User.__table__.c.id.type, PG_UUID)

    def test_username_unique(self):
        assert User.__table__.c.username.unique is True


class TestAcceptedQueryModel:
    """AcceptedQuery ORM model metadata and instantiation."""

    def test_table_name(self):
        assert AcceptedQuery.__tablename__ == "accepted_queries"

    def test_can_instantiate(self):
        aq = AcceptedQuery(
            id=uuid4(),
            user_id=uuid4(),
            database_connection_id=uuid4(),
            question_text="What are sales?",
            generated_sql="SELECT 1",
            llm_provider="ollama",
        )
        assert aq.question_text == "What are sales?"

    def test_user_id_fk(self):
        fk_tables = {fk.column.table.name for fk in AcceptedQuery.__table__.foreign_keys}
        assert "users" in fk_tables

    def test_database_connection_fk_targets_renamed_table(self):
        fk_tables = {fk.column.table.name for fk in AcceptedQuery.__table__.foreign_keys}
        assert "source_database_connections" in fk_tables


class TestSourceDatabaseConnectionModel:
    """SourceDatabaseConnection ORM model metadata and instantiation (Phase 3)."""

    def test_table_name(self):
        assert SourceDatabaseConnection.__tablename__ == "source_database_connections"

    def test_can_instantiate(self):
        dc = SourceDatabaseConnection(
            id=uuid4(),
            display_name="Production",
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database_name="analytics",
            username="readonly",
            encrypted_password="encrypted",
            ssl_mode="require",
        )
        assert dc.display_name == "Production"

    def test_lifecycle_state_default(self):
        dc = SourceDatabaseConnection(
            display_name="test",
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database_name="test",
            username="user",
            encrypted_password="enc",
            lifecycle_state=LifecycleState.ACTIVE,
        )
        assert dc.lifecycle_state == LifecycleState.ACTIVE

    def test_health_status_default(self):
        dc = SourceDatabaseConnection(
            display_name="test",
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database_name="test",
            username="user",
            encrypted_password="enc",
            health_status=HealthStatus.UNTESTED,
        )
        assert dc.health_status == HealthStatus.UNTESTED

    def test_schema_introspection_status_default(self):
        dc = SourceDatabaseConnection(
            display_name="test",
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database_name="test",
            username="user",
            encrypted_password="enc",
            schema_introspection_status=SchemaIntrospectionStatus.NONE,
        )
        assert dc.schema_introspection_status == SchemaIntrospectionStatus.NONE

    def test_has_lifecycle_state_index(self):
        indexes = {idx.name for idx in SourceDatabaseConnection.__table__.indexes}
        assert "ix_source_db_connections_lifecycle_state" in indexes


class TestAppConfigModel:
    """AppConfig ORM model metadata and instantiation."""

    def test_table_name(self):
        assert AppConfig.__tablename__ == "app_config"

    def test_can_instantiate(self):
        cfg = AppConfig(key="query_timeout_seconds", value="30")
        assert cfg.key == "query_timeout_seconds"

    def test_key_is_primary(self):
        assert AppConfig.__table__.c.key.primary_key is True
