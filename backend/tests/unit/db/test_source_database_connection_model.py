"""Tests for SourceDatabaseConnection ORM model (T-401, FR-087, FR-090)."""

import pytest
from sqlalchemy import inspect

from app.db.models.database_connection import SourceDatabaseConnection
from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus


class TestSourceDatabaseConnectionModel:
    """Verify the updated SourceDatabaseConnection model has correct columns and types."""

    def test_table_name_renamed(self):
        assert SourceDatabaseConnection.__tablename__ == "source_database_connections"

    def test_has_display_name_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "display_name" in col_names

    def test_has_database_type_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "database_type" in col_names

    def test_has_lifecycle_state_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "lifecycle_state" in col_names

    def test_has_health_status_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "health_status" in col_names

    def test_has_last_health_check_at_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "last_health_check_at" in col_names

    def test_has_health_error_category_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "health_error_category" in col_names

    def test_has_schema_introspection_status_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "schema_introspection_status" in col_names

    def test_has_schema_last_refreshed_at_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "schema_last_refreshed_at" in col_names

    def test_dropped_name_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "name" not in col_names

    def test_dropped_schema_metadata_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "schema_metadata" not in col_names

    def test_dropped_schema_cached_at_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "schema_cached_at" not in col_names

    def test_retains_host_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "host" in col_names

    def test_retains_port_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "port" in col_names

    def test_retains_database_name_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "database_name" in col_names

    def test_retains_username_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "username" in col_names

    def test_retains_encrypted_password_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "encrypted_password" in col_names

    def test_retains_ssl_mode_column(self):
        mapper = inspect(SourceDatabaseConnection)
        col_names = {c.key for c in mapper.column_attrs}
        assert "ssl_mode" in col_names

    def test_display_name_not_unique(self):
        mapper = inspect(SourceDatabaseConnection)
        col = mapper.columns["display_name"]
        assert not col.unique

    def test_lifecycle_state_default_active(self):
        """Verify lifecycle_state can be set to ACTIVE."""
        conn = SourceDatabaseConnection(
            display_name="test",
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database_name="test",
            username="user",
            encrypted_password="enc",
            lifecycle_state=LifecycleState.ACTIVE,
        )
        assert conn.lifecycle_state == LifecycleState.ACTIVE

    def test_health_status_default_untested(self):
        """Verify health_status can be set to UNTESTED."""
        conn = SourceDatabaseConnection(
            display_name="test",
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database_name="test",
            username="user",
            encrypted_password="enc",
            health_status=HealthStatus.UNTESTED,
        )
        assert conn.health_status == HealthStatus.UNTESTED

    def test_schema_introspection_status_default_none(self):
        """Verify schema_introspection_status can be set to NONE."""
        conn = SourceDatabaseConnection(
            display_name="test",
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database_name="test",
            username="user",
            encrypted_password="enc",
            schema_introspection_status=SchemaIntrospectionStatus.NONE,
        )
        assert conn.schema_introspection_status == SchemaIntrospectionStatus.NONE
