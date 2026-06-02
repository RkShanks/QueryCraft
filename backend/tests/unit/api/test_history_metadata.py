"""History API metadata response tests (T-465)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.schemas.history import AcceptedQueryDetail, HistoryListResponse
from app.schemas.query import AcceptedQuerySummary


class TestHistoryMetadata:
    @pytest.mark.asyncio
    async def test_list_history_response_includes_connection_display_metadata(self):
        from app.api.v1.history import _get_history_service, router
        from app.core.dependencies import require_active_user

        conn_id = str(uuid4())
        service = MagicMock()
        service.list_history = AsyncMock(
            return_value=HistoryListResponse(
                items=[
                    AcceptedQuerySummary(
                        id=str(uuid4()),
                        question_text="Show customers",
                        generated_sql="SELECT * FROM customers",
                        accepted_at="2026-01-01T00:00:00",
                        database_connection_id=conn_id,
                        database_connection_name="Production PG",
                        database_type="postgresql",
                    )
                ],
                total=1,
                next_cursor=None,
            )
        )

        async def override_service():
            return service

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_history_service] = override_service
        app.dependency_overrides[require_active_user] = override_user

        with patch("app.api.v1.history.require_permission", return_value=AsyncMock()):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/history")

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["database_connection_id"] == conn_id
        assert item["database_connection_name"] == "Production PG"
        assert item["database_type"] == "postgresql"

    @pytest.mark.asyncio
    async def test_history_detail_response_includes_connection_display_metadata(self):
        from unittest.mock import patch

        from app.api.v1.history import _get_history_service, router
        from app.core.dependencies import require_active_user

        conn_id = str(uuid4())
        service = MagicMock()
        service.get_detail = AsyncMock(
            return_value=AcceptedQueryDetail(
                id=str(uuid4()),
                question_text="Show customers",
                generated_sql="SELECT * FROM customers",
                llm_provider="gemini",
                accepted_at="2026-01-01T00:00:00",
                database_connection_id=conn_id,
                database_connection_name="Production PG",
                database_type="postgresql",
            )
        )

        async def override_service():
            return service

        async def override_user():
            return str(uuid4())

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_history_service] = override_service
        app.dependency_overrides[require_active_user] = override_user

        with patch("app.api.v1.history.require_permission", return_value=AsyncMock()):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/v1/history/{uuid4()}")

        assert response.status_code == 200
        detail = response.json()
        assert detail["database_connection_id"] == conn_id
        assert detail["database_connection_name"] == "Production PG"
        assert detail["database_type"] == "postgresql"
