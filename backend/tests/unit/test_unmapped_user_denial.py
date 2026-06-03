"""TDD tests for unmapped user denial (T-681).

Tests:
- Session with role_id=None → 403 error.forbidden
- Session missing role_id key → 403 error.forbidden
- Session with valid role_id but wrong permission → 403 error.forbidden (existing)
- Session with valid role_id and correct permission → 200 (existing)
- No session → 401 (existing)
- Error sanitized: no role_id value, UUIDs, usernames in response
- Built-in admin with role_id present → allowed (preserved)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException, Request
from httpx import ASGITransport, AsyncClient

from app.api.dependencies.permissions import require_permission
from app.db.models.enums import Permission


def _make_request(session_data: dict | None) -> Request:
    """Return a Request with the given session data."""
    request = MagicMock(spec=Request)
    request.state.session = session_data
    return request


def _make_app_with_session(session_data: dict | None) -> FastAPI:
    """Create a FastAPI app with middleware that injects session into request.state."""
    from fastapi.responses import JSONResponse
    from starlette.middleware.base import BaseHTTPMiddleware

    class SessionInjectionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.session = session_data
            return await call_next(request)

    async def _http_exception_handler(request, exc):
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": "error", "message_key": str(exc.detail)})

    app = FastAPI()
    app.add_middleware(SessionInjectionMiddleware)
    app.add_exception_handler(HTTPException, _http_exception_handler)
    return app


# ── Direct dependency tests ─────────────────────────────────────────────


class TestUnmappedUserDirect:
    """Direct unit tests for require_permission with unmapped users."""

    @pytest.mark.asyncio
    async def test_role_id_none_returns_403(self):
        """User with role_id=None is denied all protected access."""
        request = _make_request(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role_id": None,
                "permissions": [],
            }
        )
        dep = require_permission(Permission.QUERY_SUBMIT)
        with pytest.raises(HTTPException) as exc:
            await dep(request)
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert detail["error"] == "forbidden"
        assert detail["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_missing_role_id_returns_403(self):
        """Session missing role_id key is treated as unmapped."""
        request = _make_request(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "permissions": ["query.submit"],
            }
        )
        dep = require_permission(Permission.QUERY_SUBMIT)
        with pytest.raises(HTTPException) as exc:
            await dep(request)
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert detail["error"] == "forbidden"
        assert detail["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_empty_string_role_id_returns_403(self):
        """Empty string role_id is treated as unmapped."""
        request = _make_request(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role_id": "",
                "permissions": ["query.submit"],
            }
        )
        dep = require_permission(Permission.QUERY_SUBMIT)
        with pytest.raises(HTTPException) as exc:
            await dep(request)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_403_does_not_expose_role_id_internals(self):
        """403 response must not leak role_id value, UUIDs, or usernames."""
        request = _make_request(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role_id": None,
                "permissions": [],
                "username": "alice",
            }
        )
        dep = require_permission(Permission.QUERY_SUBMIT)
        with pytest.raises(HTTPException) as exc:
            await dep(request)
        detail_str = str(exc.value.detail).lower()
        assert "550e8400" not in detail_str
        assert "alice" not in detail_str
        assert "role_id" not in detail_str
        assert "null" not in detail_str
        assert set(exc.value.detail.keys()) == {"error", "message_key"}

    @pytest.mark.asyncio
    async def test_valid_role_id_and_correct_permission_succeeds(self):
        """User with valid role_id and correct permission is allowed."""
        request = _make_request(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "permissions": ["query.submit"],
            }
        )
        dep = require_permission(Permission.QUERY_SUBMIT)
        result = await dep(request)
        assert result == request.state.session

    @pytest.mark.asyncio
    async def test_valid_role_id_but_wrong_permission_returns_403(self):
        """User with valid role_id but wrong permission is denied."""
        request = _make_request(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "permissions": ["query.submit"],
            }
        )
        dep = require_permission(Permission.ADMIN_CONNECTIONS_MANAGE)
        with pytest.raises(HTTPException) as exc:
            await dep(request)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_no_session_returns_401(self):
        """No session still returns 401 (preserved behavior)."""
        request = _make_request(None)
        dep = require_permission(Permission.QUERY_SUBMIT)
        with pytest.raises(HTTPException) as exc:
            await dep(request)
        assert exc.value.status_code == 401


# ── Route-level tests ───────────────────────────────────────────────────


class TestUnmappedUserRouteLevel:
    """Route-level tests proving unmapped users are denied before endpoint body."""

    @pytest.mark.asyncio
    async def test_get_history_unmapped_user_returns_403(self):
        """GET /history with role_id=None returns 403, not 200 or 500."""
        from app.api.v1.history import router
        from app.core.dependencies import require_active_user

        app = _make_app_with_session(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role_id": None,
                "permissions": [],
            }
        )
        app.include_router(router, prefix="/api/v1")

        async def override_active_user():
            return "user1"

        app.dependency_overrides[require_active_user] = override_active_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history")
            assert response.status_code == 403
            data = response.json()
            assert data["error"] == "forbidden"
            assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_get_admin_settings_unmapped_user_returns_403(self):
        """GET /admin/settings with missing role_id returns 403."""
        from app.api.v1.admin import router
        from app.core.dependencies import get_db

        app = _make_app_with_session(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "permissions": ["admin.connections.manage"],
            }
        )
        app.include_router(router, prefix="/api/v1")

        app.dependency_overrides[get_db] = lambda: AsyncMock()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/settings")
            assert response.status_code == 403
            data = response.json()
            assert data["error"] == "forbidden"
            assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_post_query_submit_unmapped_user_returns_403(self):
        """POST /query/submit with role_id=None returns 403 before body validation."""
        from app.api.v1.query import router
        from app.core.dependencies import require_active_user

        app = _make_app_with_session(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role_id": None,
                "permissions": [],
            }
        )
        app.include_router(router, prefix="/api/v1")

        async def override_active_user():
            return "user1"

        app.dependency_overrides[require_active_user] = override_active_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Send completely invalid body — should still get 403, not 422
            response = await client.post("/api/v1/query/submit", json={"invalid": "data"})
            assert response.status_code == 403
            data = response.json()
            assert data["error"] == "forbidden"
            assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_unmapped_user_does_not_run_require_active_user(self):
        """Unmapped user returns 403 before require_active_user dependency executes."""
        from app.api.v1.history import router
        from app.core.dependencies import require_active_user

        app = _make_app_with_session(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role_id": None,
                "permissions": [],
            }
        )
        app.include_router(router, prefix="/api/v1")

        async def override_active_user():
            raise HTTPException(
                status_code=503,
                detail={"error": "dependency_ran", "message_key": "dependency.ran"},
            )

        app.dependency_overrides[require_active_user] = override_active_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history")
            assert response.status_code == 403
            data = response.json()
            assert data["error"] == "forbidden"
            assert data["message_key"] == "error.forbidden"
            assert "dependency_ran" not in str(data)
            assert "dependency.ran" not in str(data)

    @pytest.mark.asyncio
    async def test_mapped_user_with_correct_permission_succeeds(self):
        """User with valid role_id and correct permission can access protected endpoint."""
        from app.api.v1.history import _get_history_service, router
        from app.core.dependencies import require_active_user

        app = _make_app_with_session(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "permissions": ["query.history.view"],
            }
        )
        app.include_router(router, prefix="/api/v1")

        async def override_active_user():
            return "550e8400-e29b-41d4-a716-446655440000"

        mock_service = AsyncMock()
        from app.schemas.history import HistoryListResponse

        mock_service.list_history = AsyncMock(return_value=HistoryListResponse(items=[], total=0, next_cursor=None))

        app.dependency_overrides[require_active_user] = override_active_user
        app.dependency_overrides[_get_history_service] = lambda: mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history")
            # 200 from service means permission gate passed
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_admin_sso_providers_unmapped_user_returns_403(self):
        """GET /admin/sso/providers with missing role_id returns 403."""
        from app.api.v1.admin_sso import router

        app = _make_app_with_session(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "permissions": ["admin.sso.manage"],
            }
        )
        app.include_router(router, prefix="/api/v1")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/sso/providers")
            assert response.status_code == 403
            data = response.json()
            assert data["error"] == "forbidden"
            assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_get_admin_roles_unmapped_user_returns_403(self):
        """GET /admin/roles with missing role_id returns 403 before get_db runs."""
        from app.api.v1.admin_roles import router

        app = _make_app_with_session(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "permissions": ["admin.roles.manage"],
            }
        )
        app.include_router(router, prefix="/api/v1")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/roles")
            assert response.status_code == 403
            data = response.json()
            assert data["error"] == "forbidden"
            assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_get_admin_sso_group_mappings_unmapped_user_returns_403(self):
        """GET /admin/sso/group-mappings with missing role_id returns 403."""
        from app.api.v1.admin_sso import router

        app = _make_app_with_session(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "permissions": ["admin.roles.manage"],
            }
        )
        app.include_router(router, prefix="/api/v1")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/sso/group-mappings")
            assert response.status_code == 403
            data = response.json()
            assert data["error"] == "forbidden"
            assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_post_admin_roles_unmapped_user_invalid_body_returns_403(self):
        """POST /admin/roles with missing role_id + invalid body returns 403, not 422."""
        from app.api.v1.admin_roles import router

        app = _make_app_with_session(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "permissions": ["admin.roles.manage"],
            }
        )
        app.include_router(router, prefix="/api/v1")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/roles",
                json={"invalid": "data"},
            )
            assert response.status_code == 403
            data = response.json()
            assert data["error"] == "forbidden"
            assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_admin_roles_unmapped_user_does_not_run_get_db(self):
        """GET /admin/roles unmapped user returns 403 before get_db dependency executes."""
        from app.api.v1.admin_roles import router
        from app.core.dependencies import get_db

        app = _make_app_with_session(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "permissions": ["admin.roles.manage"],
            }
        )
        app.include_router(router, prefix="/api/v1")

        async def override_get_db():
            raise HTTPException(
                status_code=503,
                detail={"error": "dependency_ran", "message_key": "dependency.ran"},
            )

        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/roles")
            assert response.status_code == 403
            data = response.json()
            assert data["error"] == "forbidden"
            assert data["message_key"] == "error.forbidden"
            assert "dependency_ran" not in str(data)
            assert "dependency.ran" not in str(data)


class TestNonStringRoleId:
    """Non-string role_id values must be rejected (fail-closed)."""

    @pytest.mark.asyncio
    async def test_dict_role_id_returns_403(self):
        """dict role_id is treated as unmapped."""
        request = _make_request(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role_id": {},
                "permissions": ["query.submit"],
            }
        )
        dep = require_permission(Permission.QUERY_SUBMIT)
        with pytest.raises(HTTPException) as exc:
            await dep(request)
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert detail["error"] == "forbidden"
        assert detail["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_list_role_id_returns_403(self):
        """list role_id is treated as unmapped."""
        request = _make_request(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role_id": [],
                "permissions": ["query.submit"],
            }
        )
        dep = require_permission(Permission.QUERY_SUBMIT)
        with pytest.raises(HTTPException) as exc:
            await dep(request)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_int_role_id_returns_403(self):
        """int role_id is treated as unmapped."""
        request = _make_request(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role_id": 42,
                "permissions": ["query.submit"],
            }
        )
        dep = require_permission(Permission.QUERY_SUBMIT)
        with pytest.raises(HTTPException) as exc:
            await dep(request)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_bool_role_id_returns_403(self):
        """bool role_id is treated as unmapped."""
        request = _make_request(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role_id": True,
                "permissions": ["query.submit"],
            }
        )
        dep = require_permission(Permission.QUERY_SUBMIT)
        with pytest.raises(HTTPException) as exc:
            await dep(request)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_403_does_not_expose_non_string_role_id(self):
        """403 response must not leak the non-string role_id value."""
        request = _make_request(
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role_id": {"nested": "dict"},
                "permissions": [],
            }
        )
        dep = require_permission(Permission.QUERY_SUBMIT)
        with pytest.raises(HTTPException) as exc:
            await dep(request)
        detail_str = str(exc.value.detail).lower()
        assert "nested" not in detail_str
        assert "dict" not in detail_str
        assert "role_id" not in detail_str
        assert set(exc.value.detail.keys()) == {"error", "message_key"}
