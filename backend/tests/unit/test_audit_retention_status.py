"""RED unit tests for GET /admin/audit/retention (T-874).

Contract tested:
  GET /admin/audit/retention
    Permission: admin.audit.verify
    Response 200:
      {
        "retention_months": <int>,          # from Settings.AUDIT_RETENTION_MONTHS
        "last_purge_at": <ISO-8601> | null, # timestamp of latest audit.purge marker
        "purged_count": <int> | null        # purged_count from latest audit.purge context
      }

Edge cases:
  - No purge has ever run → last_purge_at=null, purged_count=null.
  - Multiple purges exist → uses the one with the highest sequence_number.
  - Missing permission → 403 with message_key.
  - No session → 403.
  - Scheduler timing is NOT in the response (external concern).

Implementation note (HTTP-level, no live DB):
  AuditService is patched at the module boundary. The endpoint is tested
  via httpx AsyncClient with dependency overrides identical to the pattern
  in test_audit_endpoints.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Helpers — identical session / app factory pattern from test_audit_endpoints.py
# ---------------------------------------------------------------------------


def _admin_session() -> dict:
    """Session with admin.audit.verify permission."""
    return {
        "user_id": str(uuid.uuid4()),
        "role_id": str(uuid.uuid4()),
        "permissions": ["admin.audit.verify"],
        "username": "admin@example.com",
    }


def _non_admin_session() -> dict:
    """Session without admin.audit.verify permission."""
    return {
        "user_id": str(uuid.uuid4()),
        "role_id": str(uuid.uuid4()),
        "permissions": ["query.submit"],
        "username": "user@example.com",
    }


def _make_app(session_data: dict | None) -> FastAPI:
    """Build a FastAPI app with session injection for the admin_audit router.

    get_db is overridden to yield a mock async session; AuditService DB calls
    are patched in individual tests so no live database is needed.
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
# T-874.1 — Permission enforcement
# ---------------------------------------------------------------------------


class TestRetentionPermissionEnforcement:
    """GET /admin/audit/retention requires admin.audit.verify permission."""

    @pytest.mark.asyncio
    async def test_no_session_returns_401(self):
        """No session → require_permission raises 401 unauthorized."""
        app = _make_app(None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/audit/retention")
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "unauthorized"
        assert data["message_key"] == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_insufficient_permission_returns_403(self):
        app = _make_app(_non_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/audit/retention")
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "forbidden"
        assert data["message_key"] == "error.forbidden"


# ---------------------------------------------------------------------------
# T-874.2 — Response shape: no purge ever
# ---------------------------------------------------------------------------


class TestRetentionResponseNoPurge:
    """When no audit.purge marker exists, last_purge_at and purged_count are null."""

    @pytest.mark.asyncio
    async def test_no_purge_returns_nulls_for_purge_fields(self):
        """With no audit.purge row, response has null last_purge_at and purged_count."""
        app = _make_app(_admin_session())

        # Mock execute to return a result where scalar_one_or_none() → None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        with patch("app.api.v1.admin_audit.get_settings") as mock_settings_fn, patch("app.core.dependencies.get_db"):
            mock_settings = MagicMock()
            mock_settings.AUDIT_RETENTION_MONTHS = 24
            mock_settings_fn.return_value = mock_settings

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # We need to patch the DB execute to return None for the purge marker query
                with patch(
                    "app.api.v1.admin_audit._get_latest_purge_marker",
                    new=AsyncMock(return_value=None),
                ):
                    response = await client.get("/api/v1/admin/audit/retention")

        assert response.status_code == 200
        data = response.json()
        assert data["last_purge_at"] is None
        assert data["purged_count"] is None

    @pytest.mark.asyncio
    async def test_no_purge_returns_retention_months_from_settings(self):
        """retention_months must come from Settings.AUDIT_RETENTION_MONTHS."""
        app = _make_app(_admin_session())

        with (
            patch("app.api.v1.admin_audit.get_settings") as mock_settings_fn,
            patch(
                "app.api.v1.admin_audit._get_latest_purge_marker",
                new=AsyncMock(return_value=None),
            ),
        ):
            mock_settings = MagicMock()
            mock_settings.AUDIT_RETENTION_MONTHS = 36
            mock_settings_fn.return_value = mock_settings

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/admin/audit/retention")

        assert response.status_code == 200
        data = response.json()
        assert data["retention_months"] == 36


# ---------------------------------------------------------------------------
# T-874.3 — Response shape: purge exists
# ---------------------------------------------------------------------------


class TestRetentionResponseWithPurge:
    """When audit.purge marker exists, last_purge_at and purged_count are populated."""

    def _make_purge_marker(self, ts: datetime, purged_count: int):
        """Build a mock AuditLogEntry representing an audit.purge marker."""
        marker = MagicMock()
        marker.timestamp = ts
        marker.context = {"purged_count": purged_count}
        return marker

    @pytest.mark.asyncio
    async def test_purge_exists_returns_last_purge_at(self):
        """last_purge_at must be the ISO-8601 timestamp of the latest purge marker."""
        ts = datetime(2026, 6, 15, 10, 30, 0, tzinfo=UTC)
        marker = self._make_purge_marker(ts, purged_count=42)

        app = _make_app(_admin_session())

        with (
            patch("app.api.v1.admin_audit.get_settings") as mock_settings_fn,
            patch(
                "app.api.v1.admin_audit._get_latest_purge_marker",
                new=AsyncMock(return_value=marker),
            ),
        ):
            mock_settings = MagicMock()
            mock_settings.AUDIT_RETENTION_MONTHS = 24
            mock_settings_fn.return_value = mock_settings

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/admin/audit/retention")

        assert response.status_code == 200
        data = response.json()
        assert data["last_purge_at"] == ts.isoformat()

    @pytest.mark.asyncio
    async def test_purge_exists_returns_purged_count(self):
        """purged_count must come from the latest audit.purge marker context."""
        ts = datetime(2026, 6, 15, 10, 30, 0, tzinfo=UTC)
        marker = self._make_purge_marker(ts, purged_count=99)

        app = _make_app(_admin_session())

        with (
            patch("app.api.v1.admin_audit.get_settings") as mock_settings_fn,
            patch(
                "app.api.v1.admin_audit._get_latest_purge_marker",
                new=AsyncMock(return_value=marker),
            ),
        ):
            mock_settings = MagicMock()
            mock_settings.AUDIT_RETENTION_MONTHS = 24
            mock_settings_fn.return_value = mock_settings

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/admin/audit/retention")

        assert response.status_code == 200
        data = response.json()
        assert data["purged_count"] == 99

    @pytest.mark.asyncio
    async def test_all_three_fields_present_in_response(self):
        """Response must always contain retention_months, last_purge_at, purged_count."""
        ts = datetime(2026, 5, 1, 0, 0, 0, tzinfo=UTC)
        marker = self._make_purge_marker(ts, purged_count=10)

        app = _make_app(_admin_session())

        with (
            patch("app.api.v1.admin_audit.get_settings") as mock_settings_fn,
            patch(
                "app.api.v1.admin_audit._get_latest_purge_marker",
                new=AsyncMock(return_value=marker),
            ),
        ):
            mock_settings = MagicMock()
            mock_settings.AUDIT_RETENTION_MONTHS = 24
            mock_settings_fn.return_value = mock_settings

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/admin/audit/retention")

        assert response.status_code == 200
        data = response.json()
        assert "retention_months" in data
        assert "last_purge_at" in data
        assert "purged_count" in data


# ---------------------------------------------------------------------------
# T-874.4 — No scheduler timing in response
# ---------------------------------------------------------------------------


class TestRetentionNoSchedulerInfo:
    """Scheduler timing must NOT appear in the response (external concern)."""

    @pytest.mark.asyncio
    async def test_no_scheduler_fields_in_response(self):
        """next_purge_at, schedule, interval, cron — must not appear in response."""
        ts = datetime(2026, 6, 15, 10, 30, 0, tzinfo=UTC)
        marker = MagicMock()
        marker.timestamp = ts
        marker.context = {"purged_count": 5}

        app = _make_app(_admin_session())

        with (
            patch("app.api.v1.admin_audit.get_settings") as mock_settings_fn,
            patch(
                "app.api.v1.admin_audit._get_latest_purge_marker",
                new=AsyncMock(return_value=marker),
            ),
        ):
            mock_settings = MagicMock()
            mock_settings.AUDIT_RETENTION_MONTHS = 24
            mock_settings_fn.return_value = mock_settings

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/admin/audit/retention")

        assert response.status_code == 200
        data = response.json()
        for forbidden_key in ("next_purge_at", "schedule", "interval", "cron"):
            assert forbidden_key not in data, f"Scheduler field {forbidden_key!r} must not appear in retention response"


# ---------------------------------------------------------------------------
# T-874.5 — purged_count=0 is treated correctly (not null)
# ---------------------------------------------------------------------------


class TestRetentionPurgedCountZero:
    """purged_count=0 in context should surface as 0, not null."""

    @pytest.mark.asyncio
    async def test_purged_count_zero_surfaces_as_zero(self):
        """A purge marker with purged_count=0 must return purged_count=0, not null."""
        ts = datetime(2026, 6, 15, 10, 30, 0, tzinfo=UTC)
        marker = MagicMock()
        marker.timestamp = ts
        marker.context = {"purged_count": 0}

        app = _make_app(_admin_session())

        with (
            patch("app.api.v1.admin_audit.get_settings") as mock_settings_fn,
            patch(
                "app.api.v1.admin_audit._get_latest_purge_marker",
                new=AsyncMock(return_value=marker),
            ),
        ):
            mock_settings = MagicMock()
            mock_settings.AUDIT_RETENTION_MONTHS = 24
            mock_settings_fn.return_value = mock_settings

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/admin/audit/retention")

        assert response.status_code == 200
        data = response.json()
        assert data["purged_count"] == 0
