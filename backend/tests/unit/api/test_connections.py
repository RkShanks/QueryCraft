"""Tests for user-facing connections endpoint (T-428, FR-077)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus


class TestUserConnectionsEndpoint:
    """Verify GET /api/v1/connections returns only active + healthy + introspected connections."""

    @pytest.mark.asyncio
    async def test_list_user_connections_empty(self):
        """No available connections returns empty list."""
        from app.api.v1.connections import router, _get_connection_service
        from app.core.dependencies import require_active_user
        from app.schemas.connection import UserConnectionListResponse
        from app.services.connection_service import ConnectionService

        mock_service = MagicMock(spec=ConnectionService)
        mock_service.list_user_available = AsyncMock(return_value=UserConnectionListResponse(connections=[]))

        async def override_service():
            return mock_service

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_connection_service] = override_service
        app.dependency_overrides[require_active_user] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/connections")
            assert response.status_code == 200
            data = response.json()
            assert data["connections"] == []

    @pytest.mark.asyncio
    async def test_list_user_connections_filters_unhealthy(self):
        """Unhealthy connections are excluded from user-facing list."""
        from app.api.v1.connections import router, _get_connection_service
        from app.core.dependencies import require_active_user
        from app.schemas.connection import UserConnectionListResponse, UserConnectionResponse
        from app.services.connection_service import ConnectionService

        conn_id = uuid4()
        available = UserConnectionListResponse(
            connections=[
                UserConnectionResponse(
                    id=conn_id,
                    display_name="Healthy PG",
                    database_type=DatabaseType.POSTGRESQL,
                )
            ]
        )

        mock_service = MagicMock(spec=ConnectionService)
        mock_service.list_user_available = AsyncMock(return_value=available)

        async def override_service():
            return mock_service

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_connection_service] = override_service
        app.dependency_overrides[require_active_user] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/connections")
            assert response.status_code == 200
            data = response.json()
            assert len(data["connections"]) == 1
            assert data["connections"][0]["id"] == str(conn_id)
            assert data["connections"][0]["display_name"] == "Healthy PG"
            assert data["connections"][0]["database_type"] == "postgresql"
            # Verify no sensitive fields leaked
            assert "host" not in data["connections"][0]
            assert "port" not in data["connections"][0]
            assert "username" not in data["connections"][0]

    @pytest.mark.asyncio
    async def test_list_user_connections_multiple_dialects(self):
        """Multiple available connections with different dialects are returned."""
        from app.api.v1.connections import router, _get_connection_service
        from app.core.dependencies import require_active_user
        from app.schemas.connection import UserConnectionListResponse, UserConnectionResponse
        from app.services.connection_service import ConnectionService

        pg_id = uuid4()
        mysql_id = uuid4()
        available = UserConnectionListResponse(
            connections=[
                UserConnectionResponse(id=pg_id, display_name="Prod PG", database_type=DatabaseType.POSTGRESQL),
                UserConnectionResponse(id=mysql_id, display_name="Prod MySQL", database_type=DatabaseType.MYSQL),
            ]
        )

        mock_service = MagicMock(spec=ConnectionService)
        mock_service.list_user_available = AsyncMock(return_value=available)

        async def override_service():
            return mock_service

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_connection_service] = override_service
        app.dependency_overrides[require_active_user] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/connections")
            assert response.status_code == 200
            data = response.json()
            assert len(data["connections"]) == 2
