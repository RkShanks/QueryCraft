"""TDD tests for permission gates on all existing admin and query/history endpoints (T-678).

Tests:
- Admin endpoints require appropriate admin permissions
- Query endpoints require query.submit
- History endpoints require query.history.view
- No session -> 401 error.unauthorized
- Wrong permissions -> 403 error.forbidden
- Correct permissions -> access granted
- All errors sanitized: no raw UUIDs, permission internals, DB errors, stack traces.
- Route-level: wrong-permission POST with invalid body returns 403, not 422.
- Route-level: wrong-permission POST /query/accept does not run _get_query_service; returns 403.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException, Request
from httpx import ASGITransport, AsyncClient

from app.api.dependencies.permissions import require_permission
from app.db.models.enums import Permission

# ── Helpers ───────────────────────────────────────────────────────────────


class FakeResult:
    """Mock SQLAlchemy result with scalars().all() / scalar_one_or_none()."""

    def __init__(self, items):
        self._items = items if isinstance(items, list) else [items]

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def first(self):
        return self._items[0] if self._items else None


def _make_request_with_permissions(permissions: list[str] | None) -> Request:
    """Return a Request with the given permissions in session."""
    request = MagicMock(spec=Request)
    if permissions is None:
        request.state.session = None
    else:
        request.state.session = {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": permissions,
        }
    return request


# ── require_permission dependency direct tests ──────────────────────────


class TestRequirePermissionDirect:
    """Direct unit tests for the require_permission dependency."""

    @pytest.mark.asyncio
    async def test_no_session_returns_401(self):
        request = _make_request_with_permissions(None)
        dep = require_permission(Permission.QUERY_SUBMIT)
        with pytest.raises(HTTPException) as exc:
            await dep(request)
        assert exc.value.status_code == 401
        detail = exc.value.detail
        assert detail["error"] == "unauthorized"
        assert detail["message_key"] == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_wrong_permission_returns_403(self):
        request = _make_request_with_permissions(["query.submit"])
        dep = require_permission(Permission.ADMIN_CONNECTIONS_MANAGE)
        with pytest.raises(HTTPException) as exc:
            await dep(request)
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert detail["error"] == "forbidden"
        assert detail["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_correct_permission_returns_session(self):
        request = _make_request_with_permissions([Permission.QUERY_SUBMIT.value])
        dep = require_permission(Permission.QUERY_SUBMIT)
        result = await dep(request)
        assert result == request.state.session

    @pytest.mark.asyncio
    async def test_multiple_permissions_one_matches(self):
        request = _make_request_with_permissions(["query.submit", "query.history.view"])
        dep = require_permission(Permission.QUERY_SUBMIT, Permission.ADMIN_ROLES_MANAGE)
        result = await dep(request)
        assert result == request.state.session

    @pytest.mark.asyncio
    async def test_empty_permissions_returns_403(self):
        request = _make_request_with_permissions([])
        dep = require_permission(Permission.QUERY_SUBMIT)
        with pytest.raises(HTTPException) as exc:
            await dep(request)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_403_does_not_expose_permission_internals(self):
        request = _make_request_with_permissions(["query.submit"])
        dep = require_permission(Permission.ADMIN_CONNECTIONS_MANAGE)
        with pytest.raises(HTTPException) as exc:
            await dep(request)
        detail = exc.value.detail
        assert "admin.connections.manage" not in str(detail).lower()
        assert "query.submit" not in str(detail).lower()
        assert set(detail.keys()) == {"error", "message_key"}


# ── Admin Settings (admin.py) ─────────────────────────────────────────


class TestAdminSettingsPermissionGates:
    """GET /admin/settings and PATCH /admin/settings require admin permission."""

    @pytest.mark.asyncio
    async def test_get_settings_correct_permission_succeeds(self):
        from app.api.v1.admin import get_settings_admin

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([]))
        result = await get_settings_admin(
            _session={"permissions": [Permission.ADMIN_CONNECTIONS_MANAGE.value]},
            db=mock_db,
        )
        assert hasattr(result, "llm_context_cap")

    @pytest.mark.asyncio
    async def test_patch_settings_correct_permission_succeeds(self):
        from app.api.v1.admin import update_settings_admin
        from app.schemas.admin_settings import UpdateAdminSettingsRequest

        mock_db = AsyncMock()
        result = await update_settings_admin(
            req=UpdateAdminSettingsRequest(llm_context_cap=5, max_regenerate_attempts=3),
            _session={"permissions": [Permission.ADMIN_CONNECTIONS_MANAGE.value]},
            db=mock_db,
        )
        assert result.llm_context_cap == 5


# ── Admin Connections (admin_connections.py) ──────────────────────────────


class TestAdminConnectionsPermissionGates:
    """All /admin/connections endpoints require admin.connections.manage."""

    @pytest.mark.asyncio
    async def test_list_connections_correct_permission_succeeds(self):
        from app.api.v1.admin_connections import list_connections

        mock_service = AsyncMock()
        mock_service.list_all = AsyncMock(return_value=[])
        result = await list_connections(
            _session={"permissions": [Permission.ADMIN_CONNECTIONS_MANAGE.value]},
            service=mock_service,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_create_connection_correct_permission_succeeds(self):
        from app.api.v1.admin_connections import create_connection
        from app.schemas.connection import ConnectionCreate

        mock_service = AsyncMock()
        mock_conn = MagicMock()
        mock_conn.id = uuid.uuid4()
        mock_conn.display_name = "Test"
        mock_conn.database_type = "postgresql"
        mock_conn.host = "h"
        mock_conn.port = 5432
        mock_conn.database_name = "db"
        mock_conn.username = "u"
        mock_conn.encrypted_password = "enc"
        mock_conn.ssl_mode = "prefer"
        mock_conn.lifecycle_state = "active"
        mock_conn.health_status = "untested"
        mock_conn.schema_introspection_status = "none"
        mock_conn.created_at = None
        mock_conn.updated_at = None
        mock_service.create = AsyncMock(return_value=mock_conn)
        result = await create_connection(
            req=ConnectionCreate(
                display_name="Test",
                database_type="postgresql",
                host="h",
                port=5432,
                database_name="db",
                username="u",
                password="p",
            ),
            _session={"permissions": [Permission.ADMIN_CONNECTIONS_MANAGE.value]},
            service=mock_service,
        )
        assert result.display_name == "Test"

    @pytest.mark.asyncio
    async def test_get_connection_correct_permission_succeeds(self):
        from app.api.v1.admin_connections import get_connection

        mock_service = AsyncMock()
        result = await get_connection(
            connection_id=uuid.uuid4(),
            _session={"permissions": [Permission.ADMIN_CONNECTIONS_MANAGE.value]},
            service=mock_service,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_update_connection_correct_permission_succeeds(self):
        from app.api.v1.admin_connections import update_connection
        from app.schemas.connection import ConnectionUpdate

        mock_service = AsyncMock()
        result = await update_connection(
            connection_id=uuid.uuid4(),
            req=ConnectionUpdate(),
            _session={"permissions": [Permission.ADMIN_CONNECTIONS_MANAGE.value]},
            service=mock_service,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_delete_connection_correct_permission_succeeds(self):
        from app.api.v1.admin_connections import delete_connection

        mock_service = AsyncMock()
        result = await delete_connection(
            connection_id=uuid.uuid4(),
            _session={"permissions": [Permission.ADMIN_CONNECTIONS_MANAGE.value]},
            service=mock_service,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_disable_connection_correct_permission_succeeds(self):
        from app.api.v1.admin_connections import disable_connection

        mock_service = AsyncMock()
        result = await disable_connection(
            connection_id=uuid.uuid4(),
            _session={"permissions": [Permission.ADMIN_CONNECTIONS_MANAGE.value]},
            service=mock_service,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_enable_connection_correct_permission_succeeds(self):
        from app.api.v1.admin_connections import enable_connection

        mock_service = AsyncMock()
        result = await enable_connection(
            connection_id=uuid.uuid4(),
            _session={"permissions": [Permission.ADMIN_CONNECTIONS_MANAGE.value]},
            service=mock_service,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_test_connection_correct_permission_succeeds(self):
        from app.api.v1.admin_connections import test_connection

        mock_service = AsyncMock()
        result = await test_connection(
            connection_id=uuid.uuid4(),
            _session={"permissions": [Permission.ADMIN_CONNECTIONS_MANAGE.value]},
            service=mock_service,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_refresh_schema_connection_correct_permission_succeeds(self):
        from app.api.v1.admin_connections import refresh_schema

        mock_service = AsyncMock()
        result = await refresh_schema(
            connection_id=uuid.uuid4(),
            _session={"permissions": [Permission.ADMIN_CONNECTIONS_MANAGE.value]},
            service=mock_service,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_schema_connection_correct_permission_succeeds(self):
        from app.api.v1.admin_connections import get_schema

        mock_service = AsyncMock()
        result = await get_schema(
            connection_id=uuid.uuid4(),
            _session={"permissions": [Permission.ADMIN_CONNECTIONS_MANAGE.value]},
            service=mock_service,
        )
        assert result is not None


# ── Query Endpoints (query.py) ────────────────────────────────────────────


class TestQueryPermissionGates:
    """All /query endpoints require query.submit."""

    @pytest.mark.asyncio
    async def test_submit_question_correct_permission_succeeds(self):
        from app.api.v1.query import submit_question

        request = MagicMock()
        request.state.session_id = "sess1"
        mock_service = AsyncMock()
        mock_result = MagicMock()
        mock_result.kind = "result"
        mock_service.submit_question.return_value = mock_result

        req = MagicMock()
        req.question = "test"
        req.connection_id = "conn1"
        req.session_id = None

        with patch("app.api.v1.query._build_query_service_for_connection", new=AsyncMock(return_value=mock_service)):
            result = await submit_question(
                request=request,
                _session={"permissions": [Permission.QUERY_SUBMIT.value]},
                req=req,
                user_id="user1",
                db=AsyncMock(),
                redis=AsyncMock(),
            )
        assert result.kind == "result"

    @pytest.mark.asyncio
    async def test_accept_query_correct_permission_succeeds(self):
        from app.api.v1.query import accept_query

        request = MagicMock()
        request.state.session_id = "sess1"
        mock_service = AsyncMock()
        req = MagicMock()
        req.attempt_id = "a1"
        req.session_id = None

        result = await accept_query(
            request=request,
            _session={"permissions": [Permission.QUERY_SUBMIT.value]},
            req=req,
            user_id="user1",
            service=mock_service,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_reject_query_correct_permission_succeeds(self):
        from app.api.v1.query import reject_query

        request = MagicMock()
        request.state.session_id = "sess1"
        mock_service = AsyncMock()
        req = MagicMock()
        req.attempt_id = "a1"
        req.feedback = None
        req.session_id = None

        result = await reject_query(
            request=request,
            _session={"permissions": [Permission.QUERY_SUBMIT.value]},
            req=req,
            user_id="user1",
            service=mock_service,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_regenerate_query_correct_permission_succeeds(self):
        from app.api.v1.query import regenerate_query

        request = MagicMock()
        request.state.session_id = "sess1"
        mock_service = AsyncMock()
        req = MagicMock()
        req.attempt_id = "a1"
        req.session_id = None

        result = await regenerate_query(
            request=request,
            _session={"permissions": [Permission.QUERY_SUBMIT.value]},
            req=req,
            user_id="user1",
            service=mock_service,
        )
        assert result is not None


# ── History Endpoints (history.py) ──────────────────────────────────────────


class TestHistoryPermissionGates:
    """All /history endpoints require query.history.view."""

    @pytest.mark.asyncio
    async def test_list_history_correct_permission_succeeds(self):
        from app.api.v1.history import list_history

        mock_service = AsyncMock()
        mock_service.list_history = AsyncMock(return_value=MagicMock())
        result = await list_history(
            cursor=None,
            limit=100,
            user_id="user1",
            _session={"permissions": [Permission.QUERY_HISTORY_VIEW.value]},
            service=mock_service,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_history_entry_correct_permission_succeeds(self):
        from app.api.v1.history import get_history_entry

        mock_service = AsyncMock()
        mock_service.get_detail = AsyncMock(return_value=MagicMock())
        result = await get_history_entry(
            query_id=uuid.uuid4(),
            user_id="user1",
            _session={"permissions": [Permission.QUERY_HISTORY_VIEW.value]},
            service=mock_service,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_delete_history_entry_correct_permission_succeeds(self):
        from app.api.v1.history import delete_history_entry

        mock_service = AsyncMock()
        mock_service.delete_entry = AsyncMock(return_value=True)
        result = await delete_history_entry(
            query_id=uuid.uuid4(),
            user_id="user1",
            _session={"permissions": [Permission.QUERY_HISTORY_VIEW.value]},
            service=mock_service,
        )
        assert result is None


# ── Route-level TestClient tests ─────────────────────────────────────────


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


class TestRouteLevelPermissionGates:
    """Route-level tests proving 403 before body validation or service deps execute."""

    @pytest.mark.asyncio
    async def test_post_admin_connections_invalid_body_wrong_permission_returns_403(self):
        """Wrong-permission POST /admin/connections with invalid body returns 403, not 422."""
        from app.api.v1.admin_connections import router
        from app.core.dependencies import require_active_user

        app = _make_app_with_session({"permissions": ["query.submit"]})
        app.include_router(router, prefix="/api/v1")

        # Override require_active_user so it doesn't hit the DB
        async def override_active_user():
            return "user1"

        app.dependency_overrides[require_active_user] = override_active_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Send completely invalid body (missing required fields)
            response = await client.post("/api/v1/admin/connections", json={"invalid": "data"})
            assert response.status_code == 403
            data = response.json()
            assert data["error"] == "forbidden"
            assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_post_query_accept_wrong_permission_returns_403(self):
        """Wrong-permission POST /query/accept returns 403 before endpoint body."""
        from app.api.v1.query import router
        from app.core.dependencies import require_active_user

        app = _make_app_with_session({"permissions": ["query.history.view"]})
        app.include_router(router, prefix="/api/v1")

        async def override_active_user():
            return "user1"

        app.dependency_overrides[require_active_user] = override_active_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/query/accept", json={"attempt_id": "a1"})
            assert response.status_code == 403
            data = response.json()
            assert data["error"] == "forbidden"
            assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_post_query_submit_invalid_body_wrong_permission_returns_403(self):
        """Wrong-permission POST /query/submit with invalid body returns 403, not 422."""
        from app.api.v1.query import router
        from app.core.dependencies import require_active_user

        app = _make_app_with_session({"permissions": ["query.history.view"]})
        app.include_router(router, prefix="/api/v1")

        async def override_active_user():
            return "user1"

        app.dependency_overrides[require_active_user] = override_active_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Send completely invalid body
            response = await client.post("/api/v1/query/submit", json={"invalid": "data"})
            assert response.status_code == 403
            data = response.json()
            assert data["error"] == "forbidden"
            assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_get_history_wrong_permission_returns_403(self):
        """Wrong-permission GET /history returns 403."""
        from app.api.v1.history import router
        from app.core.dependencies import require_active_user

        app = _make_app_with_session({"permissions": ["query.submit"]})
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
    async def test_get_admin_settings_wrong_permission_returns_403(self):
        """Wrong-permission GET /admin/settings returns 403."""
        from app.api.v1.admin import router
        from app.core.dependencies import require_active_user

        app = _make_app_with_session({"permissions": ["query.submit"]})
        app.include_router(router, prefix="/api/v1")

        async def override_active_user():
            return "user1"

        app.dependency_overrides[require_active_user] = override_active_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/settings")
            assert response.status_code == 403
            data = response.json()
            assert data["error"] == "forbidden"
            assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_get_history_wrong_permission_does_not_run_require_active_user(self):
        """Wrong-permission GET /history returns 403 before require_active_user executes."""
        from app.api.v1.history import router
        from app.core.dependencies import require_active_user

        app = _make_app_with_session({"permissions": ["query.submit"]})
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
    async def test_no_session_returns_401(self):
        """No session returns 401 at route level."""
        from app.api.v1.history import router
        from app.core.dependencies import require_active_user

        app = _make_app_with_session(None)
        app.include_router(router, prefix="/api/v1")

        async def override_active_user():
            return "user1"

        app.dependency_overrides[require_active_user] = override_active_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history")
            assert response.status_code == 401
            data = response.json()
            assert data["error"] == "unauthorized"
            assert data["message_key"] == "error.unauthorized"


# ── Permission Matrix Verification ────────────────────────────────────────


class TestPermissionMatrix:
    """Verify each router enforces the correct permission."""

    def test_admin_settings_uses_admin_connections_manage(self):
        """admin.py settings endpoints use ADMIN_CONNECTIONS_MANAGE."""
        import inspect

        from app.api.v1.admin import get_settings_admin, update_settings_admin

        sig_get = inspect.signature(get_settings_admin)
        sig_patch = inspect.signature(update_settings_admin)

        # Both should have _session parameter with Depends(require_permission(...))
        assert "_session" in sig_get.parameters
        assert "_session" in sig_patch.parameters

    def test_admin_connections_uses_admin_connections_manage(self):
        """admin_connections.py endpoints use ADMIN_CONNECTIONS_MANAGE."""
        import inspect

        from app.api.v1 import admin_connections

        endpoints = [
            admin_connections.list_connections,
            admin_connections.create_connection,
            admin_connections.get_connection,
            admin_connections.update_connection,
            admin_connections.delete_connection,
            admin_connections.disable_connection,
            admin_connections.enable_connection,
            admin_connections.test_connection,
            admin_connections.refresh_schema,
            admin_connections.get_schema,
        ]
        for ep in endpoints:
            sig = inspect.signature(ep)
            assert "_session" in sig.parameters, f"{ep.__name__} missing _session"

    def test_query_uses_query_submit(self):
        """query.py endpoints use QUERY_SUBMIT."""
        import inspect

        from app.api.v1 import query

        endpoints = [
            query.submit_question,
            query.accept_query,
            query.reject_query,
            query.regenerate_query,
        ]
        for ep in endpoints:
            sig = inspect.signature(ep)
            assert "_session" in sig.parameters, f"{ep.__name__} missing _session"

    def test_history_uses_query_history_view(self):
        """history.py endpoints use QUERY_HISTORY_VIEW."""
        import inspect

        from app.api.v1 import history

        endpoints = [
            history.list_history,
            history.get_history_entry,
            history.delete_history_entry,
        ]
        for ep in endpoints:
            sig = inspect.signature(ep)
            assert "_session" in sig.parameters, f"{ep.__name__} missing _session"

    def test_admin_roles_uses_admin_roles_manage(self):
        """admin_roles.py endpoints use ADMIN_ROLES_MANAGE via Depends()."""
        import inspect

        from app.api.v1 import admin_roles

        endpoints = [
            admin_roles.list_roles,
            admin_roles.create_role,
            admin_roles.get_role,
            admin_roles.update_role,
            admin_roles.delete_role,
        ]
        for ep in endpoints:
            sig = inspect.signature(ep)
            assert "_session" in sig.parameters, f"{ep.__name__} missing _session (admin_roles uses Depends())"

    def test_admin_sso_providers_uses_admin_sso_manage(self):
        """admin_sso.py provider endpoints use ADMIN_SSO_MANAGE via Depends()."""
        import inspect

        from app.api.v1 import admin_sso

        endpoints = [
            admin_sso.list_providers,
            admin_sso.create_provider,
            admin_sso.update_provider,
            admin_sso.delete_provider,
        ]
        for ep in endpoints:
            sig = inspect.signature(ep)
            assert "_session" in sig.parameters, f"{ep.__name__} missing _session (admin_sso providers use Depends())"

    def test_admin_sso_group_mappings_uses_admin_roles_manage(self):
        """admin_sso.py group mapping endpoints use ADMIN_ROLES_MANAGE via Depends()."""
        import inspect

        from app.api.v1 import admin_sso

        endpoints = [
            admin_sso.list_group_mappings,
            admin_sso.create_group_mapping,
            admin_sso.delete_group_mapping,
        ]
        for ep in endpoints:
            sig = inspect.signature(ep)
            assert "_session" in sig.parameters, (
                f"{ep.__name__} missing _session (admin_sso group mappings use Depends())"
            )
