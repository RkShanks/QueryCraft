"""Tests for Phase 3 database enums (T-400)."""

from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus


class TestDatabaseType:
    """Verify DatabaseType enum values."""

    def test_postgresql_value(self):
        assert DatabaseType.POSTGRESQL.value == "postgresql"

    def test_mysql_value(self):
        assert DatabaseType.MYSQL.value == "mysql"

    def test_mssql_value(self):
        assert DatabaseType.MSSQL.value == "mssql"

    def test_all_types_count(self):
        assert len(DatabaseType) == 3


class TestLifecycleState:
    """Verify LifecycleState enum values."""

    def test_active_value(self):
        assert LifecycleState.ACTIVE.value == "active"

    def test_disabled_value(self):
        assert LifecycleState.DISABLED.value == "disabled"

    def test_all_states_count(self):
        assert len(LifecycleState) == 2


class TestHealthStatus:
    """Verify HealthStatus enum values."""

    def test_untested_value(self):
        assert HealthStatus.UNTESTED.value == "untested"

    def test_healthy_value(self):
        assert HealthStatus.HEALTHY.value == "healthy"

    def test_unhealthy_value(self):
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_all_statuses_count(self):
        assert len(HealthStatus) == 3


class TestSchemaIntrospectionStatus:
    """Verify SchemaIntrospectionStatus enum values."""

    def test_none_value(self):
        assert SchemaIntrospectionStatus.NONE.value == "none"

    def test_success_value(self):
        assert SchemaIntrospectionStatus.SUCCESS.value == "success"

    def test_failed_value(self):
        assert SchemaIntrospectionStatus.FAILED.value == "failed"

    def test_stale_value(self):
        assert SchemaIntrospectionStatus.STALE.value == "stale"

    def test_all_statuses_count(self):
        assert len(SchemaIntrospectionStatus) == 4
