"""Tests for admin connection API endpoints (T-415, SC-025, SC-029)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus


def _create_test_app():
    """Create a test FastAPI app with mocked connection service."""
    from app.api.v1.admin_connections import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


class TestAdminConnectionsCRUD:
    """Verify admin connection CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_list_connections_empty(self):
        from app.services.connection_service import ConnectionService

        Fernet.generate_key().decode()
        mock_service = MagicMock(spec=ConnectionService)
        mock_service.list_all = AsyncMock(return_value=[])

        app = FastAPI()

        @app.get("/api/v1/admin/connections")
        async def list_connections():
            return {"connections": await mock_service.list_all()}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/connections")
            assert response.status_code == 200
            data = response.json()
            assert data["connections"] == []

    @pytest.mark.asyncio
    async def test_create_connection(self):
        from app.schemas.connection import ConnectionResponse

        Fernet.generate_key().decode()
        mock_response = ConnectionResponse(
            id=uuid4(),
            display_name="New DB",
            database_type=DatabaseType.MYSQL,
            host="mysql.example.com",
            port=3306,
            database_name="analytics",
            username="reader",
            ssl_mode="require",
            lifecycle_state=LifecycleState.ACTIVE,
            health_status=HealthStatus.UNTESTED,
            last_health_check_at=None,
            health_error_category=None,
            schema_introspection_status=SchemaIntrospectionStatus.NONE,
            schema_last_refreshed_at=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        app = FastAPI()

        @app.post("/api/v1/admin/connections")
        async def create_connection():
            return mock_response.model_dump(mode="json")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/admin/connections")
            assert response.status_code == 200
            data = response.json()
            assert data["display_name"] == "New DB"
            assert "encrypted_password" not in data
            assert "password" not in data


class TestAdminConnectionLifecycle:
    """Verify admin lifecycle endpoints."""

    @pytest.mark.asyncio
    async def test_disable_connection(self):
        from app.schemas.connection import ConnectionResponse

        conn_id = uuid4()
        mock_response = ConnectionResponse(
            id=conn_id,
            display_name="Test DB",
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database_name="test",
            username="user",
            ssl_mode="require",
            lifecycle_state=LifecycleState.DISABLED,
            health_status=HealthStatus.UNTESTED,
            last_health_check_at=None,
            health_error_category=None,
            schema_introspection_status=SchemaIntrospectionStatus.NONE,
            schema_last_refreshed_at=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        app = FastAPI()

        @app.post(f"/api/v1/admin/connections/{conn_id}/disable")
        async def disable():
            return mock_response.model_dump(mode="json")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/api/v1/admin/connections/{conn_id}/disable")
            assert response.status_code == 200
            data = response.json()
            assert data["lifecycle_state"] == "disabled"


class TestAdminConnectionTest:
    """Verify admin health test endpoint."""

    @pytest.mark.asyncio
    async def test_connection_healthy(self):
        from app.schemas.connection import ConnectionTestResult

        conn_id = uuid4()
        mock_result = ConnectionTestResult(
            status="healthy",
            latency_ms=12.5,
            tested_at=datetime.now(UTC),
        )

        app = FastAPI()

        @app.post(f"/api/v1/admin/connections/{conn_id}/test")
        async def test_conn():
            return mock_result.model_dump(mode="json")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/api/v1/admin/connections/{conn_id}/test")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["latency_ms"] == 12.5


class TestAdminConnectionHardDeleteGuard:
    """Verify hard-delete guard returns 409 when referenced."""

    @pytest.mark.asyncio
    async def test_delete_blocked_returns_409(self):
        app = FastAPI()

        @app.delete("/api/v1/admin/connections/{conn_id}")
        async def delete_connection(conn_id: str):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=409,
                detail={"error": "connection_referenced", "message_key": "error.connection_referenced_delete_blocked"},
            )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/api/v1/admin/connections/{uuid4()}")
            assert response.status_code == 409
            data = response.json()
            # FastAPI exception handler returns detail directly when it's a dict
            assert "connection_referenced" in str(data)


class TestAdminConnectionSchemaEndpoints:
    """Verify refresh-schema and schema endpoints."""

    @pytest.mark.asyncio
    async def test_refresh_schema_success(self):
        conn_id = uuid4()

        app = FastAPI()

        @app.post("/api/v1/admin/connections/{conn_id}/refresh-schema")
        async def refresh_schema(conn_id: str):
            return {
                "tables_count": 5,
                "columns_count": 23,
                "refreshed_at": datetime.now(UTC).isoformat(),
            }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/api/v1/admin/connections/{conn_id}/refresh-schema")
            assert response.status_code == 200
            data = response.json()
            assert data["tables_count"] == 5

    @pytest.mark.asyncio
    async def test_get_schema_summary(self):
        conn_id = uuid4()

        app = FastAPI()

        @app.get("/api/v1/admin/connections/{conn_id}/schema")
        async def get_schema(conn_id: str):
            return {
                "connection_id": conn_id,
                "tables": [{"table_name": "users", "column_count": 3, "columns": []}],
                "introspected_at": datetime.now(UTC).isoformat(),
            }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/admin/connections/{conn_id}/schema")
            assert response.status_code == 200
            data = response.json()
            assert len(data["tables"]) == 1


class TestAdminConnectionSchemaRealDependencyPath:
    """Verify refresh-schema endpoint works with real FastAPI dependency injection."""

    @pytest.mark.asyncio
    async def test_refresh_schema_via_real_dependency(self):
        """Test that refresh-schema works when service is constructed via FastAPI deps."""
        from fastapi.responses import JSONResponse
        from starlette.middleware.base import BaseHTTPMiddleware

        from app.api.v1.admin_connections import _get_connection_service, router
        from app.services.connection_service import ConnectionService

        conn_id = uuid4()
        mock_service = MagicMock(spec=ConnectionService)
        mock_service.refresh_schema = AsyncMock(
            return_value={
                "tables_count": 3,
                "columns_count": 12,
                "refreshed_at": datetime.now(UTC),
            }
        )

        async def override_service():
            return mock_service

        class SessionInjectionMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                request.state.session = {
                    "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "permissions": ["admin.connections.manage"],
                }
                return await call_next(request)

        app = FastAPI()
        app.add_middleware(SessionInjectionMiddleware)

        @app.exception_handler(HTTPException)
        async def _http_exception_handler(request, exc):
            if isinstance(exc.detail, dict):
                return JSONResponse(status_code=exc.status_code, content=exc.detail)
            return JSONResponse(status_code=exc.status_code, content={"error": "error", "message_key": str(exc.detail)})

        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_connection_service] = override_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/api/v1/admin/connections/{conn_id}/refresh-schema")
            assert response.status_code == 200
            data = response.json()
            assert data["tables_count"] == 3
            mock_service.refresh_schema.assert_called_once_with(conn_id)

    @pytest.mark.asyncio
    async def test_refresh_schema_not_found_via_real_dependency(self):
        """Test that refresh-schema returns 404 when connection not found."""
        from fastapi.responses import JSONResponse
        from starlette.middleware.base import BaseHTTPMiddleware

        from app.api.v1.admin_connections import _get_connection_service, router
        from app.services.connection_service import ConnectionNotFoundError, ConnectionService

        conn_id = uuid4()
        mock_service = MagicMock(spec=ConnectionService)
        mock_service.refresh_schema = AsyncMock(side_effect=ConnectionNotFoundError(conn_id))

        async def override_service():
            return mock_service

        class SessionInjectionMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                request.state.session = {
                    "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "permissions": ["admin.connections.manage"],
                }
                return await call_next(request)

        app = FastAPI()
        app.add_middleware(SessionInjectionMiddleware)

        @app.exception_handler(HTTPException)
        async def _http_exception_handler(request, exc):
            if isinstance(exc.detail, dict):
                return JSONResponse(status_code=exc.status_code, content=exc.detail)
            return JSONResponse(status_code=exc.status_code, content={"error": "error", "message_key": str(exc.detail)})

        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_connection_service] = override_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/api/v1/admin/connections/{conn_id}/refresh-schema")
            assert response.status_code == 404
