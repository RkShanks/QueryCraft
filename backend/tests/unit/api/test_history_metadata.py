"""History API metadata response tests (T-465)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.schemas.history import AcceptedQueryDetail, HistoryListResponse
from app.schemas.query import AcceptedQuerySummary


class TestHistoryMetadata:
    @pytest.mark.asyncio
    async def test_list_history_response_includes_connection_display_metadata(self):
        from fastapi.responses import JSONResponse
        from starlette.middleware.base import BaseHTTPMiddleware

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

        class SessionInjectionMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                request.state.session = {"permissions": ["query.history.view"]}
                return await call_next(request)

        app = FastAPI()
        app.add_middleware(SessionInjectionMiddleware)

        @app.exception_handler(HTTPException)
        async def _http_exception_handler(request, exc):
            if isinstance(exc.detail, dict):
                return JSONResponse(status_code=exc.status_code, content=exc.detail)
            return JSONResponse(status_code=exc.status_code, content={"error": "error", "message_key": str(exc.detail)})

        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_history_service] = override_service
        app.dependency_overrides[require_active_user] = override_user

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
        from fastapi.responses import JSONResponse
        from starlette.middleware.base import BaseHTTPMiddleware

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

        class SessionInjectionMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                request.state.session = {"permissions": ["query.history.view"]}
                return await call_next(request)

        app = FastAPI()
        app.add_middleware(SessionInjectionMiddleware)

        @app.exception_handler(HTTPException)
        async def _http_exception_handler(request, exc):
            if isinstance(exc.detail, dict):
                return JSONResponse(status_code=exc.status_code, content=exc.detail)
            return JSONResponse(status_code=exc.status_code, content={"error": "error", "message_key": str(exc.detail)})

        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[_get_history_service] = override_service
        app.dependency_overrides[require_active_user] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/history/{uuid4()}")

        assert response.status_code == 200
        detail = response.json()
        assert detail["database_connection_id"] == conn_id
        assert detail["database_connection_name"] == "Production PG"
        assert detail["database_type"] == "postgresql"
