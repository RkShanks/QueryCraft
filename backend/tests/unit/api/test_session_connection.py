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
        from app.api.v1.sessions import router, _get_session_repo
        from app.core.dependencies import require_active_user

        session_id = uuid4()
        conn_id = uuid4()

        mock_repo = MagicMock()
        mock_repo.update_connection = AsyncMock(
            return_value={
                "id": str(session_id),
                "connection_id": str(conn_id),
                "preview_text": "Test session",
                "created_at": "2026-01-01T00:00:00",
                "last_activity_at": "2026-01-01T00:00:00",
            }
        )

        async def override_repo():
            return mock_repo

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_session_repo] = override_repo
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
        from app.api.v1.sessions import router, _get_session_repo
        from app.core.dependencies import require_active_user

        session_id = uuid4()
        conn_id = uuid4()

        mock_repo = MagicMock()
        mock_repo.update_connection = AsyncMock(return_value=None)

        async def override_repo():
            return mock_repo

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_session_repo] = override_repo
        app.dependency_overrides[require_active_user] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/sessions/{session_id}/connection",
                json={"connection_id": str(conn_id)},
            )
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_session_connection_invalid(self):
        """Invalid/unhealthy connection returns 400."""
        from app.api.v1.sessions import router, _get_session_repo
        from app.core.dependencies import require_active_user

        session_id = uuid4()
        conn_id = uuid4()

        mock_repo = MagicMock()
        mock_repo.update_connection = AsyncMock(side_effect=ValueError("Connection not available"))

        async def override_repo():
            return mock_repo

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_session_repo] = override_repo
        app.dependency_overrides[require_active_user] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/sessions/{session_id}/connection",
                json={"connection_id": str(conn_id)},
            )
            assert response.status_code == 400
