"""Tests for ORM model instantiation and metadata (T-042).

Asserts User, AcceptedQuery, DatabaseConnection, AppConfig models can be instantiated,
have correct table names, and column types match data-model.md.
"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import Integer, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

from app.db.models.accepted_query import AcceptedQuery
from app.db.models.app_config import AppConfig
from app.db.models.database_connection import DatabaseConnection
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
        fk = list(AcceptedQuery.__table__.foreign_keys)[0]
        assert fk.column.table.name == "users"


class TestDatabaseConnectionModel:
    """DatabaseConnection ORM model metadata and instantiation."""

    def test_table_name(self):
        assert DatabaseConnection.__tablename__ == "database_connections"

    def test_can_instantiate(self):
        dc = DatabaseConnection(
            id=uuid4(),
            name="Production",
            host="localhost",
            port=5432,
            database_name="analytics",
            username="readonly",
            encrypted_password="encrypted",
            ssl_mode="require",
        )
        assert dc.name == "Production"

    def test_schema_metadata_jsonb(self):
        assert isinstance(DatabaseConnection.__table__.c.schema_metadata.type, JSONB)


class TestAppConfigModel:
    """AppConfig ORM model metadata and instantiation."""

    def test_table_name(self):
        assert AppConfig.__tablename__ == "app_config"

    def test_can_instantiate(self):
        cfg = AppConfig(key="query_timeout_seconds", value="30")
        assert cfg.key == "query_timeout_seconds"

    def test_key_is_primary(self):
        assert AppConfig.__table__.c.key.primary_key is True
