"""HTTP contract for audit filter-context creation (CHUNK-28)."""

from __future__ import annotations

import base64
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.admin_audit import router as admin_audit_router
from app.core.dependencies import get_db, get_redis
from app.schemas.audit_search import AuditSearchPagination, AuditSearchResponse
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

    async def _mock_get_redis():
        yield MagicMock()

    async def _http_exception_handler(_request, exc):
        content = exc.detail if isinstance(exc.detail, dict) else {"error": "error"}
        return JSONResponse(status_code=exc.status_code, content=content)

    async def _validation_exception_handler(_request, _exc):
        return JSONResponse(
            status_code=422,
            content={"error": "validation", "message_key": "error.validation.generic"},
        )

    app = FastAPI()
    use_test_session_current_role(app)
    app.add_middleware(SessionInjectionMiddleware)
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.dependency_overrides[get_db] = _mock_get_db
    app.dependency_overrides[get_redis] = _mock_get_redis
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


@pytest.mark.asyncio
async def test_search_and_export_resolve_the_same_context_without_raw_filters_in_requests():
    canary = "actor-sensitive-canary"
    app = _filter_context_app(_admin_session())
    captured_search_actor: str | None = None
    captured_export_actor: str | None = None

    async def _search(_db, params, _retention_months):
        nonlocal captured_search_actor
        captured_search_actor = params.actor_identity
        return AuditSearchResponse(
            entries=[],
            pagination=AuditSearchPagination(
                page=params.page, page_size=params.page_size, total_entries=0, total_pages=1
            ),
        )

    async def _export(_db, _retention_months, **filters):
        nonlocal captured_export_actor
        captured_export_actor = filters["actor_identity"]
        return 0, []

    with (
        patch("app.api.v1.admin_audit.AuditSearchService.search", new=_search),
        patch("app.api.v1.admin_audit.AuditSearchService.get_all_entries_for_export", new=_export),
        patch("app.api.v1.admin_audit.QuotaService.check_and_increment", new=AsyncMock()),
        patch("app.api.v1.admin_audit.AuditService.log", new=AsyncMock()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            issued = await client.post(
                "/api/v1/admin/audit/filter-context",
                json={"actor_identity": canary},
            )
            token = issued.json()["filter_context"]
            search = await client.get(
                "/api/v1/admin/audit/entries",
                params={"filter_context": token, "page": 2, "page_size": 10},
            )
            export = await client.post(
                "/api/v1/admin/audit/export",
                json={"format": "json", "filter_context": token},
            )

    assert canary not in str(search.request.url)
    assert captured_search_actor == canary
    assert captured_export_actor == canary
    assert search.headers["cache-control"] == "no-store"
    assert export.headers["cache-control"] == "no-store"
    assert canary not in search.text
    assert canary not in export.text


@pytest.mark.asyncio
async def test_invalid_contexts_use_one_sanitized_error_for_search_and_export():
    app = _filter_context_app(_admin_session())
    invalid_context = base64.b64encode(b"malformed-context").decode()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        search = await client.get(
            "/api/v1/admin/audit/entries",
            params={"filter_context": invalid_context},
        )
        export = await client.post(
            "/api/v1/admin/audit/export",
            json={"format": "csv", "filter_context": invalid_context},
        )

    expected = {
        "error": "invalid_filter_context",
        "message_key": "error.audit_filter_context_invalid",
    }
    assert search.status_code == 422
    assert export.status_code == 422
    assert search.json() == expected
    assert export.json() == expected


@pytest.mark.asyncio
async def test_mixed_context_and_raw_filters_are_rejected_without_echoing_values():
    canary = "actor-sensitive-canary"
    app = _filter_context_app(_admin_session())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        issued = await client.post(
            "/api/v1/admin/audit/filter-context",
            json={"actor_identity": canary},
        )
        token = issued.json()["filter_context"]
        search = await client.get(
            "/api/v1/admin/audit/entries",
            params={"filter_context": token, "actor_identity": canary},
        )
        export = await client.post(
            "/api/v1/admin/audit/export",
            json={"format": "json", "filter_context": token, "actor_identity": canary},
        )

    assert search.status_code == 422
    assert export.status_code == 422
    assert canary not in search.text
    assert canary not in export.text
