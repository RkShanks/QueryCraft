"""RED security tests for audit search/export/retention permission gates (T-877).

Contract under test:
  GET  /admin/audit/entries   — requires admin.audit.verify
  POST /admin/audit/export    — requires admin.audit.verify
  GET  /admin/audit/retention — requires admin.audit.verify

Three scenarios per endpoint:
  1. No session (request.state.session is None)      → 401 error.unauthorized
  2. Session missing admin.audit.verify permission   → 403 error.forbidden
  3. Session WITH admin.audit.verify                 → non-403 (endpoint logic runs)

These are pure permission-gate tests; no live DB or real service calls.
AuditSearchService, AuditExportService, and the retention helper are all
patched at the module boundary so that HTTP-layer assertions remain
independent of business logic correctness.

FR/SC: FR-166, FR-167, FR-172, SC-068, SC-069, SC-070, SC-074
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def _admin_session() -> dict:
    """Session dict with admin.audit.verify permission."""
    return {
        "user_id": str(uuid.uuid4()),
        "role_id": str(uuid.uuid4()),
        "permissions": ["admin.audit.verify"],
        "username": "admin@example.com",
    }


def _non_admin_session() -> dict:
    """Session dict without admin.audit.verify (only query.submit)."""
    return {
        "user_id": str(uuid.uuid4()),
        "role_id": str(uuid.uuid4()),
        "permissions": ["query.submit"],
        "username": "user@example.com",
    }


# ---------------------------------------------------------------------------
# App factory — identical pattern to test_audit_retention_status.py
# ---------------------------------------------------------------------------


def _make_app(session_data: dict | None) -> FastAPI:
    """Build a minimal FastAPI app wired to admin_audit router.

    * SessionInjectionMiddleware injects ``session_data`` into
      ``request.state.session`` before every request.
    * ``get_db`` is overridden to yield a no-op async session so no
      live database connection is required.
    * ``HTTPException`` handler serialises ``exc.detail`` as JSON in the
      expected ``{error, message_key}`` shape.
    """
    from fastapi.responses import JSONResponse
    from starlette.middleware.base import BaseHTTPMiddleware

    from app.api.v1.admin_audit import router as admin_audit_router
    from app.core.dependencies import get_db

    class SessionInjectionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.session = session_data
            return await call_next(request)

    async def _http_exc_handler(request, exc):
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "error", "message_key": str(exc.detail)},
        )

    async def _mock_get_db():
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.execute = AsyncMock()
        yield mock_session

    app = FastAPI()
    app.add_middleware(SessionInjectionMiddleware)
    app.add_exception_handler(HTTPException, _http_exc_handler)
    app.dependency_overrides[get_db] = _mock_get_db
    app.include_router(admin_audit_router, prefix="/api/v1")
    return app


# ---------------------------------------------------------------------------
# Minimal stubs used when an authorised admin request passes the gate
# ---------------------------------------------------------------------------


def _stub_search_response():
    """Return a minimal AuditSearchResponse-like dict for patching."""
    from app.schemas.audit_search import AuditSearchPagination, AuditSearchResponse

    return AuditSearchResponse(
        entries=[],
        pagination=AuditSearchPagination(
            page=1, page_size=50, total_entries=0, total_pages=1
        ),
    )


# ---------------------------------------------------------------------------
# T-877-A  GET /admin/audit/entries — permission gates
# ---------------------------------------------------------------------------


class TestSearchEntriesPermissionGate:
    """GET /admin/audit/entries must be gated by admin.audit.verify."""

    @pytest.mark.asyncio
    async def test_no_session_returns_401(self):
        """No session (None) → 401 error.unauthorized."""
        app = _make_app(None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/audit/entries")
        assert response.status_code == 401
        data = response.json()
        assert data.get("error") == "unauthorized"
        assert data.get("message_key") == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_missing_permission_returns_403(self):
        """Session without admin.audit.verify → 403 error.forbidden."""
        app = _make_app(_non_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/audit/entries")
        assert response.status_code == 403
        data = response.json()
        assert data.get("error") == "forbidden"
        assert data.get("message_key") == "error.forbidden"

    @pytest.mark.asyncio
    async def test_with_permission_passes_gate(self):
        """Session WITH admin.audit.verify → not 401/403 (gate passed)."""
        app = _make_app(_admin_session())
        transport = ASGITransport(app=app)

        stub_response = _stub_search_response()
        with patch(
            "app.services.audit_search_service.AuditSearchService.search",
            new=AsyncMock(return_value=stub_response),
        ):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/admin/audit/entries")

        assert response.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# T-877-B  POST /admin/audit/export — permission gates
# ---------------------------------------------------------------------------


class TestExportPermissionGate:
    """POST /admin/audit/export must be gated by admin.audit.verify."""

    @pytest.mark.asyncio
    async def test_no_session_returns_401(self):
        """No session → 401 error.unauthorized."""
        app = _make_app(None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/audit/export",
                json={"format": "csv"},
            )
        assert response.status_code == 401
        data = response.json()
        assert data.get("error") == "unauthorized"
        assert data.get("message_key") == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_missing_permission_returns_403(self):
        """Session without admin.audit.verify → 403 error.forbidden."""
        app = _make_app(_non_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/audit/export",
                json={"format": "csv"},
            )
        assert response.status_code == 403
        data = response.json()
        assert data.get("error") == "forbidden"
        assert data.get("message_key") == "error.forbidden"

    @pytest.mark.asyncio
    async def test_with_permission_passes_gate(self):
        """Session WITH admin.audit.verify → not 401/403 (gate passed)."""
        from app.core.exceptions import QuotaUnavailableError

        app = _make_app(_admin_session())
        transport = ASGITransport(app=app)

        # Stub export path: quota check raises QuotaUnavailableError so we can
        # assert a non-403 status (503) without wiring real export logic.
        with patch(
            "app.services.quota_service.QuotaService.check_and_increment",
            new=AsyncMock(side_effect=QuotaUnavailableError()),
        ):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/admin/audit/export",
                    json={"format": "csv"},
                )

        assert response.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# T-877-C  GET /admin/audit/retention — permission gates
# ---------------------------------------------------------------------------


class TestRetentionPermissionGate:
    """GET /admin/audit/retention must be gated by admin.audit.verify."""

    @pytest.mark.asyncio
    async def test_no_session_returns_401(self):
        """No session → 401 error.unauthorized."""
        app = _make_app(None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/audit/retention")
        assert response.status_code == 401
        data = response.json()
        assert data.get("error") == "unauthorized"
        assert data.get("message_key") == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_missing_permission_returns_403(self):
        """Session without admin.audit.verify → 403 error.forbidden."""
        app = _make_app(_non_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/audit/retention")
        assert response.status_code == 403
        data = response.json()
        assert data.get("error") == "forbidden"
        assert data.get("message_key") == "error.forbidden"

    @pytest.mark.asyncio
    async def test_with_permission_passes_gate(self):
        """Session WITH admin.audit.verify → not 401/403 (gate passed)."""
        app = _make_app(_admin_session())
        transport = ASGITransport(app=app)

        with (
            patch(
                "app.api.v1.admin_audit.get_settings",
            ) as mock_settings_fn,
            patch(
                "app.api.v1.admin_audit._get_latest_purge_marker",
                new=AsyncMock(return_value=None),
            ),
        ):
            mock_settings = MagicMock()
            mock_settings.AUDIT_RETENTION_MONTHS = 24
            mock_settings_fn.return_value = mock_settings

            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/admin/audit/retention")

        assert response.status_code not in (401, 403)
