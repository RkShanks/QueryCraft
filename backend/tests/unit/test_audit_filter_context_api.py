"""HTTP contract for audit filter-context creation (CHUNK-28)."""

from __future__ import annotations

import base64
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.admin_audit import router as admin_audit_router
from app.core.dependencies import get_db
from tests.unit.permission_test_helpers import use_test_session_current_role


def _admin_session() -> dict[str, object]:
    return {
        "user_id": str(uuid.uuid4()),
        "role_id": str(uuid.uuid4()),
        "permissions": ["admin.audit.verify"],
        "username": "admin@example.com",
    }


def _filter_context_app(session: dict[str, object], session_id: str = "http-session-a") -> FastAPI:
    class SessionInjectionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.session = session
            request.state.session_id = session_id
            return await call_next(request)

    async def _mock_get_db():
        database_session = MagicMock()
        database_session.commit = AsyncMock()
        database_session.execute = AsyncMock()
        yield database_session

    async def _http_exception_handler(_request, exc):
        content = exc.detail if isinstance(exc.detail, dict) else {"error": "error"}
        return JSONResponse(status_code=exc.status_code, content=content)

    app = FastAPI()
    use_test_session_current_role(app)
    app.add_middleware(SessionInjectionMiddleware)
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.dependency_overrides[get_db] = _mock_get_db
    app.include_router(admin_audit_router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
async def test_context_endpoint_returns_only_opaque_value_safe_metadata():
    canary = "actor-sensitive-canary"
    app = _filter_context_app(_admin_session())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/audit/filter-context",
            json={"actor_identity": canary, "expires_in_seconds": 300},
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert set(response.json()) == {"filter_context", "applied_fields", "expires_at"}
    assert response.json()["applied_fields"] == ["actor_identity"]
    assert canary not in response.text
    assert canary not in base64.b64decode(response.json()["filter_context"]).decode("utf-8", errors="ignore")
