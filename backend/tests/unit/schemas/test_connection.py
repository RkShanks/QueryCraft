"""Tests for connection Pydantic schemas (T-411, FR-059, FR-060)."""

import pytest
from uuid import uuid4
from datetime import datetime, timezone

from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus
from app.schemas.connection import (
    ConnectionCreate,
    ConnectionUpdate,
    ConnectionResponse,
    ConnectionTestResult,
    ConnectionListResponse,
)


class TestConnectionCreate:
    """Verify ConnectionCreate schema validation."""

    def test_valid_create(self):
        req = ConnectionCreate(
            display_name="Test DB",
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database_name="test",
            username="user",
            password="secret",
        )
        assert req.display_name == "Test DB"
        assert req.ssl_mode == "require"

    def test_empty_display_name_rejected(self):
        with pytest.raises(Exception):
            ConnectionCreate(
                display_name="",
                database_type=DatabaseType.POSTGRESQL,
                host="localhost",
                port=5432,
                database_name="test",
                username="user",
                password="secret",
            )

    def test_port_out_of_range_rejected(self):
        with pytest.raises(Exception):
            ConnectionCreate(
                display_name="Test DB",
                database_type=DatabaseType.POSTGRESQL,
                host="localhost",
                port=99999,
                database_name="test",
                username="user",
                password="secret",
            )

    def test_empty_password_rejected(self):
        with pytest.raises(Exception):
            ConnectionCreate(
                display_name="Test DB",
                database_type=DatabaseType.POSTGRESQL,
                host="localhost",
                port=5432,
                database_name="test",
                username="user",
                password="",
            )


class TestConnectionUpdate:
    """Verify ConnectionUpdate schema validation."""

    def test_partial_update(self):
        req = ConnectionUpdate(display_name="New Name")
        assert req.display_name == "New Name"
        assert req.host is None

    def test_null_password_keeps_existing(self):
        req = ConnectionUpdate(password=None)
        assert req.password is None


class TestConnectionResponse:
    """Verify ConnectionResponse schema."""

    def test_from_orm_model(self):
        from app.db.models.database_connection import SourceDatabaseConnection

        conn = SourceDatabaseConnection(
            id=uuid4(),
            display_name="Test DB",
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database_name="test",
            username="user",
            encrypted_password="encrypted",
            ssl_mode="require",
            lifecycle_state=LifecycleState.ACTIVE,
            health_status=HealthStatus.HEALTHY,
            last_health_check_at=datetime.now(timezone.utc),
            health_error_category=None,
            schema_introspection_status=SchemaIntrospectionStatus.SUCCESS,
            schema_last_refreshed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        resp = ConnectionResponse.model_validate(conn)
        assert resp.display_name == "Test DB"
        assert resp.database_type == DatabaseType.POSTGRESQL
        # Password is NOT in response
        assert not hasattr(resp, "encrypted_password")


class TestConnectionTestResult:
    """Verify ConnectionTestResult schema."""

    def test_healthy_result(self):
        result = ConnectionTestResult(
            status="healthy",
            latency_ms=12.5,
            tested_at=datetime.now(timezone.utc),
        )
        assert result.status == "healthy"
        assert result.error_category is None

    def test_unhealthy_result(self):
        result = ConnectionTestResult(
            status="unhealthy",
            error_category="auth_failed",
            message_key="error.connection_auth_failed",
            tested_at=datetime.now(timezone.utc),
        )
        assert result.status == "unhealthy"
        assert result.latency_ms is None


class TestConnectionListResponse:
    """Verify ConnectionListResponse schema."""

    def test_empty_list(self):
        resp = ConnectionListResponse(connections=[])
        assert len(resp.connections) == 0
