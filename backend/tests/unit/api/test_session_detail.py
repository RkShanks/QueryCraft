"""Tests for GET /sessions/{id} endpoint (T-460)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


class TestSessionDetail:
    """Verify GET /sessions/{session_id} includes connection_id."""

    @pytest.mark.asyncio
    async def test_get_session_detail_includes_connection_id(self):
        """Session detail response includes connection_id when assigned."""
        from app.api.v1.sessions import (
            _get_accepted_query_repo,
            _get_session_repo,
            router,
        )
        from app.core.dependencies import require_active_user

        session_id = uuid4()
        conn_id = uuid4()

        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.connection_id = conn_id
        mock_session.preview_text = "Test session"
        mock_session.created_at.isoformat.return_value = "2026-01-01T00:00:00"
        mock_session.last_activity_at.isoformat.return_value = "2026-01-01T00:00:00"

        mock_session_repo = MagicMock()
        mock_session_repo.get_by_id = AsyncMock(return_value=mock_session)

        mock_query_repo = MagicMock()
        mock_query_repo.list_by_session = AsyncMock(return_value=[])

        async def override_session_repo():
            return mock_session_repo

        async def override_query_repo():
            return mock_query_repo

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_session_repo] = override_session_repo
        app.dependency_overrides[_get_accepted_query_repo] = override_query_repo
        app.dependency_overrides[require_active_user] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/sessions/{session_id}",
            )
            assert response.status_code == 200
            data = response.json()
            assert data["connection_id"] == str(conn_id)
            assert "attempts" in data

    @pytest.mark.asyncio
    async def test_get_session_detail_connection_id_null_when_unassigned(self):
        """Session detail response includes connection_id as null when unassigned."""
        from app.api.v1.sessions import (
            _get_accepted_query_repo,
            _get_session_repo,
            router,
        )
        from app.core.dependencies import require_active_user

        session_id = uuid4()

        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.connection_id = None
        mock_session.preview_text = "Test session"
        mock_session.created_at.isoformat.return_value = "2026-01-01T00:00:00"
        mock_session.last_activity_at.isoformat.return_value = "2026-01-01T00:00:00"

        mock_session_repo = MagicMock()
        mock_session_repo.get_by_id = AsyncMock(return_value=mock_session)

        mock_query_repo = MagicMock()
        mock_query_repo.list_by_session = AsyncMock(return_value=[])

        async def override_session_repo():
            return mock_session_repo

        async def override_query_repo():
            return mock_query_repo

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_session_repo] = override_session_repo
        app.dependency_overrides[_get_accepted_query_repo] = override_query_repo
        app.dependency_overrides[require_active_user] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/sessions/{session_id}",
            )
            assert response.status_code == 200
            data = response.json()
            assert "connection_id" in data
            assert data["connection_id"] is None
