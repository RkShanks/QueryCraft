"""Tests for PATCH /sessions/{id}/connection endpoint (T-434, FR-094)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


class TestSessionConnectionUpdate:
    """Verify PATCH /sessions/{session_id}/connection endpoint."""

    @pytest.mark.asyncio
    async def test_update_session_connection_success(self):
        """Valid connection update returns updated session."""
        from app.api.v1.sessions import (
            _get_connection_repo,
            _get_session_repo,
            router,
        )
        from app.core.dependencies import require_active_user

        session_id = uuid4()
        conn_id = uuid4()

        mock_conn = MagicMock()
        mock_conn.lifecycle_state = "active"
        mock_conn.health_status = "healthy"
        mock_conn.schema_introspection_status = "success"

        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.connection_id = conn_id
        mock_session.preview_text = "Test session"
        mock_session.created_at.isoformat.return_value = "2026-01-01T00:00:00"
        mock_session.last_activity_at.isoformat.return_value = "2026-01-01T00:00:00"

        mock_conn_repo = MagicMock()
        mock_conn_repo.get_by_id = AsyncMock(return_value=mock_conn)

        mock_session_repo = MagicMock()
        mock_session_repo.update_connection = AsyncMock(return_value=mock_session)

        async def override_conn_repo():
            return mock_conn_repo

        async def override_session_repo():
            return mock_session_repo

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_connection_repo] = override_conn_repo
        app.dependency_overrides[_get_session_repo] = override_session_repo
        app.dependency_overrides[require_active_user] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/sessions/{session_id}/connection",
                json={"connection_id": str(conn_id)},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["connection_id"] == str(conn_id)

    @pytest.mark.asyncio
    async def test_update_session_connection_not_found(self):
        """Non-existent session returns 404."""
        from app.api.v1.sessions import (
            _get_connection_repo,
            _get_session_repo,
            router,
        )
        from app.core.dependencies import require_active_user

        session_id = uuid4()
        conn_id = uuid4()

        mock_conn = MagicMock()
        mock_conn.lifecycle_state = "active"
        mock_conn.health_status = "healthy"
        mock_conn.schema_introspection_status = "success"

        mock_conn_repo = MagicMock()
        mock_conn_repo.get_by_id = AsyncMock(return_value=mock_conn)

        mock_session_repo = MagicMock()
        mock_session_repo.update_connection = AsyncMock(return_value=None)

        async def override_conn_repo():
            return mock_conn_repo

        async def override_session_repo():
            return mock_session_repo

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_connection_repo] = override_conn_repo
        app.dependency_overrides[_get_session_repo] = override_session_repo
        app.dependency_overrides[require_active_user] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/sessions/{session_id}/connection",
                json={"connection_id": str(conn_id)},
            )
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_session_connection_not_found_in_db(self):
        """Non-existent connection returns 400."""
        from app.api.v1.sessions import (
            _get_connection_repo,
            _get_session_repo,
            router,
        )
        from app.core.dependencies import require_active_user

        session_id = uuid4()
        conn_id = uuid4()

        mock_conn_repo = MagicMock()
        mock_conn_repo.get_by_id = AsyncMock(return_value=None)

        mock_session_repo = MagicMock()

        async def override_conn_repo():
            return mock_conn_repo

        async def override_session_repo():
            return mock_session_repo

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_connection_repo] = override_conn_repo
        app.dependency_overrides[_get_session_repo] = override_session_repo
        app.dependency_overrides[require_active_user] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/sessions/{session_id}/connection",
                json={"connection_id": str(conn_id)},
            )
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_session_connection_disabled(self):
        """Disabled connection returns 400."""
        from app.api.v1.sessions import (
            _get_connection_repo,
            _get_session_repo,
            router,
        )
        from app.core.dependencies import require_active_user

        session_id = uuid4()
        conn_id = uuid4()

        mock_conn = MagicMock()
        mock_conn.lifecycle_state = "disabled"
        mock_conn.health_status = "healthy"
        mock_conn.schema_introspection_status = "success"

        mock_conn_repo = MagicMock()
        mock_conn_repo.get_by_id = AsyncMock(return_value=mock_conn)

        mock_session_repo = MagicMock()

        async def override_conn_repo():
            return mock_conn_repo

        async def override_session_repo():
            return mock_session_repo

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_connection_repo] = override_conn_repo
        app.dependency_overrides[_get_session_repo] = override_session_repo
        app.dependency_overrides[require_active_user] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/sessions/{session_id}/connection",
                json={"connection_id": str(conn_id)},
            )
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_session_connection_unhealthy(self):
        """Unhealthy connection returns 400."""
        from app.api.v1.sessions import (
            _get_connection_repo,
            _get_session_repo,
            router,
        )
        from app.core.dependencies import require_active_user

        session_id = uuid4()
        conn_id = uuid4()

        mock_conn = MagicMock()
        mock_conn.lifecycle_state = "active"
        mock_conn.health_status = "unhealthy"
        mock_conn.schema_introspection_status = "success"

        mock_conn_repo = MagicMock()
        mock_conn_repo.get_by_id = AsyncMock(return_value=mock_conn)

        mock_session_repo = MagicMock()

        async def override_conn_repo():
            return mock_conn_repo

        async def override_session_repo():
            return mock_session_repo

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_connection_repo] = override_conn_repo
        app.dependency_overrides[_get_session_repo] = override_session_repo
        app.dependency_overrides[require_active_user] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/sessions/{session_id}/connection",
                json={"connection_id": str(conn_id)},
            )
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_session_connection_no_schema(self):
        """Non-introspected connection returns 400."""
        from app.api.v1.sessions import (
            _get_connection_repo,
            _get_session_repo,
            router,
        )
        from app.core.dependencies import require_active_user

        session_id = uuid4()
        conn_id = uuid4()

        mock_conn = MagicMock()
        mock_conn.lifecycle_state = "active"
        mock_conn.health_status = "healthy"
        mock_conn.schema_introspection_status = "pending"

        mock_conn_repo = MagicMock()
        mock_conn_repo.get_by_id = AsyncMock(return_value=mock_conn)

        mock_session_repo = MagicMock()

        async def override_conn_repo():
            return mock_conn_repo

        async def override_session_repo():
            return mock_session_repo

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_connection_repo] = override_conn_repo
        app.dependency_overrides[_get_session_repo] = override_session_repo
        app.dependency_overrides[require_active_user] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/sessions/{session_id}/connection",
                json={"connection_id": str(conn_id)},
            )
            assert response.status_code == 400
