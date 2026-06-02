"""TDD tests for permission gates on all existing admin and query/history endpoints (T-678).

Tests:
- Admin endpoints require appropriate admin permissions
- Query endpoints require query.submit
- History endpoints require query.history.view
- No session -> 401 error.unauthorized
- Wrong permissions -> 403 error.forbidden
- Correct permissions -> access granted
- All errors sanitized: no raw UUIDs, permission internals, DB errors, stack traces.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

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


def _make_request_with_permissions(permissions: list[str] | None) -> MagicMock:
    """Return a mock Request with the given permissions in session."""
    request = MagicMock()
    if permissions is None:
        request.state.session = None
    else:
        request.state.session = {"user_id": "550e8400-e29b-41d4-a716-446655440000", "permissions": permissions}
    return request


# ── Admin Settings (admin.py) ─────────────────────────────────────────────


class TestAdminSettingsPermissionGates:
    """GET /admin/settings and PATCH /admin/settings require admin permission."""

    @pytest.mark.asyncio
    async def test_get_settings_no_session_returns_401(self):
        from app.api.v1.admin import get_settings_admin

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await get_settings_admin(request=request, db=AsyncMock())
        assert exc.value.status_code == 401
        detail = exc.value.detail
        assert detail["error"] == "unauthorized"
        assert detail["message_key"] == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_get_settings_wrong_permission_returns_403(self):
        from app.api.v1.admin import get_settings_admin

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await get_settings_admin(request=request, db=AsyncMock())
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert detail["error"] == "forbidden"
        assert detail["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_get_settings_correct_permission_succeeds(self):
        from app.api.v1.admin import get_settings_admin

        request = _make_request_with_permissions([Permission.ADMIN_CONNECTIONS_MANAGE.value])
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([]))
        result = await get_settings_admin(request=request, db=mock_db)
        assert hasattr(result, "llm_context_cap")

    @pytest.mark.asyncio
    async def test_patch_settings_no_session_returns_401(self):
        from app.api.v1.admin import update_settings_admin
        from app.schemas.admin_settings import UpdateAdminSettingsRequest

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await update_settings_admin(
                request=request,
                req=UpdateAdminSettingsRequest(llm_context_cap=5, max_regenerate_attempts=3),
                db=AsyncMock(),
            )
        assert exc.value.status_code == 401
        detail = exc.value.detail
        assert detail["error"] == "unauthorized"
        assert detail["message_key"] == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_patch_settings_wrong_permission_returns_403(self):
        from app.api.v1.admin import update_settings_admin
        from app.schemas.admin_settings import UpdateAdminSettingsRequest

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await update_settings_admin(
                request=request,
                req=UpdateAdminSettingsRequest(llm_context_cap=5, max_regenerate_attempts=3),
                db=AsyncMock(),
            )
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert detail["error"] == "forbidden"
        assert detail["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_patch_settings_correct_permission_succeeds(self):
        from app.api.v1.admin import update_settings_admin
        from app.schemas.admin_settings import UpdateAdminSettingsRequest

        request = _make_request_with_permissions([Permission.ADMIN_CONNECTIONS_MANAGE.value])
        mock_db = AsyncMock()
        result = await update_settings_admin(
            request=request,
            req=UpdateAdminSettingsRequest(llm_context_cap=5, max_regenerate_attempts=3),
            db=mock_db,
        )
        assert result.llm_context_cap == 5


# ── Admin Connections (admin_connections.py) ──────────────────────────────


class TestAdminConnectionsPermissionGates:
    """All /admin/connections endpoints require admin.connections.manage."""

    @pytest.mark.asyncio
    async def test_list_connections_no_session_returns_401(self):
        from app.api.v1.admin_connections import list_connections

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await list_connections(request=request, service=AsyncMock())
        assert exc.value.status_code == 401
        detail = exc.value.detail
        assert detail["error"] == "unauthorized"
        assert detail["message_key"] == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_list_connections_wrong_permission_returns_403(self):
        from app.api.v1.admin_connections import list_connections

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await list_connections(request=request, service=AsyncMock())
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert detail["error"] == "forbidden"
        assert detail["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_list_connections_correct_permission_succeeds(self):
        from app.api.v1.admin_connections import list_connections

        request = _make_request_with_permissions([Permission.ADMIN_CONNECTIONS_MANAGE.value])
        mock_service = AsyncMock()
        mock_service.list_all = AsyncMock(return_value=[])
        result = await list_connections(request=request, service=mock_service)
        assert result == []

    @pytest.mark.asyncio
    async def test_create_connection_no_session_returns_401(self):
        from app.api.v1.admin_connections import create_connection
        from app.schemas.connection import ConnectionCreate

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await create_connection(
                request=request,
                req=ConnectionCreate(
                    display_name="Test",
                    database_type="postgresql",
                    host="h",
                    port=5432,
                    database_name="db",
                    username="u",
                    password="p",
                ),
                service=AsyncMock(),
            )
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_create_connection_wrong_permission_returns_403(self):
        from app.api.v1.admin_connections import create_connection
        from app.schemas.connection import ConnectionCreate

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await create_connection(
                request=request,
                req=ConnectionCreate(
                    display_name="Test",
                    database_type="postgresql",
                    host="h",
                    port=5432,
                    database_name="db",
                    username="u",
                    password="p",
                ),
                service=AsyncMock(),
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_create_connection_correct_permission_succeeds(self):
        from app.api.v1.admin_connections import create_connection
        from app.schemas.connection import ConnectionCreate

        request = _make_request_with_permissions([Permission.ADMIN_CONNECTIONS_MANAGE.value])
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
            request=request,
            req=ConnectionCreate(
                display_name="Test",
                database_type="postgresql",
                host="h",
                port=5432,
                database_name="db",
                username="u",
                password="p",
            ),
            service=mock_service,
        )
        assert result.display_name == "Test"

    @pytest.mark.asyncio
    async def test_get_connection_no_session_returns_401(self):
        from app.api.v1.admin_connections import get_connection

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await get_connection(request=request, connection_id=uuid.uuid4(), service=AsyncMock())
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_connection_wrong_permission_returns_403(self):
        from app.api.v1.admin_connections import get_connection

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await get_connection(request=request, connection_id=uuid.uuid4(), service=AsyncMock())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_update_connection_no_session_returns_401(self):
        from app.api.v1.admin_connections import update_connection
        from app.schemas.connection import ConnectionUpdate

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await update_connection(
                request=request,
                connection_id=uuid.uuid4(),
                req=ConnectionUpdate(),
                service=AsyncMock(),
            )
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_update_connection_wrong_permission_returns_403(self):
        from app.api.v1.admin_connections import update_connection
        from app.schemas.connection import ConnectionUpdate

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await update_connection(
                request=request,
                connection_id=uuid.uuid4(),
                req=ConnectionUpdate(),
                service=AsyncMock(),
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_connection_no_session_returns_401(self):
        from app.api.v1.admin_connections import delete_connection

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await delete_connection(request=request, connection_id=uuid.uuid4(), service=AsyncMock())
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_connection_wrong_permission_returns_403(self):
        from app.api.v1.admin_connections import delete_connection

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await delete_connection(request=request, connection_id=uuid.uuid4(), service=AsyncMock())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_disable_connection_no_session_returns_401(self):
        from app.api.v1.admin_connections import disable_connection

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await disable_connection(request=request, connection_id=uuid.uuid4(), service=AsyncMock())
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_disable_connection_wrong_permission_returns_403(self):
        from app.api.v1.admin_connections import disable_connection

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await disable_connection(request=request, connection_id=uuid.uuid4(), service=AsyncMock())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_enable_connection_no_session_returns_401(self):
        from app.api.v1.admin_connections import enable_connection

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await enable_connection(request=request, connection_id=uuid.uuid4(), service=AsyncMock())
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_enable_connection_wrong_permission_returns_403(self):
        from app.api.v1.admin_connections import enable_connection

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await enable_connection(request=request, connection_id=uuid.uuid4(), service=AsyncMock())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_test_connection_no_session_returns_401(self):
        from app.api.v1.admin_connections import test_connection

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await test_connection(request=request, connection_id=uuid.uuid4(), service=AsyncMock())
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_test_connection_wrong_permission_returns_403(self):
        from app.api.v1.admin_connections import test_connection

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await test_connection(request=request, connection_id=uuid.uuid4(), service=AsyncMock())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_refresh_schema_connection_no_session_returns_401(self):
        from app.api.v1.admin_connections import refresh_schema

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await refresh_schema(request=request, connection_id=uuid.uuid4(), service=AsyncMock())
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_schema_connection_wrong_permission_returns_403(self):
        from app.api.v1.admin_connections import refresh_schema

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await refresh_schema(request=request, connection_id=uuid.uuid4(), service=AsyncMock())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_schema_connection_no_session_returns_401(self):
        from app.api.v1.admin_connections import get_schema

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await get_schema(request=request, connection_id=uuid.uuid4(), service=AsyncMock())
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_schema_connection_wrong_permission_returns_403(self):
        from app.api.v1.admin_connections import get_schema

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await get_schema(request=request, connection_id=uuid.uuid4(), service=AsyncMock())
        assert exc.value.status_code == 403


# ── Query Endpoints (query.py) ────────────────────────────────────────────


class TestQueryPermissionGates:
    """All /query endpoints require query.submit."""

    @pytest.mark.asyncio
    async def test_submit_question_no_session_returns_401(self):
        from app.api.v1.query import submit_question

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await submit_question(
                request=request,
                req=MagicMock(question="test", connection_id="conn1", session_id=None),
                user_id="user1",
                db=AsyncMock(),
                redis=AsyncMock(),
            )
        assert exc.value.status_code == 401
        detail = exc.value.detail
        assert detail["error"] == "unauthorized"
        assert detail["message_key"] == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_submit_question_wrong_permission_returns_403(self):
        from app.api.v1.query import submit_question

        request = _make_request_with_permissions(["query.history.view"])
        with pytest.raises(HTTPException) as exc:
            await submit_question(
                request=request,
                req=MagicMock(question="test", connection_id="conn1", session_id=None),
                user_id="user1",
                db=AsyncMock(),
                redis=AsyncMock(),
            )
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert detail["error"] == "forbidden"
        assert detail["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_accept_query_no_session_returns_401(self):
        from app.api.v1.query import accept_query

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await accept_query(
                request=request,
                req=MagicMock(attempt_id="a1", session_id=None),
                user_id="user1",
                service=AsyncMock(),
            )
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_accept_query_wrong_permission_returns_403(self):
        from app.api.v1.query import accept_query

        request = _make_request_with_permissions(["query.history.view"])
        with pytest.raises(HTTPException) as exc:
            await accept_query(
                request=request,
                req=MagicMock(attempt_id="a1", session_id=None),
                user_id="user1",
                service=AsyncMock(),
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_reject_query_no_session_returns_401(self):
        from app.api.v1.query import reject_query

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await reject_query(
                request=request,
                req=MagicMock(attempt_id="a1", feedback=None, session_id=None),
                user_id="user1",
                service=AsyncMock(),
            )
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_reject_query_wrong_permission_returns_403(self):
        from app.api.v1.query import reject_query

        request = _make_request_with_permissions(["query.history.view"])
        with pytest.raises(HTTPException) as exc:
            await reject_query(
                request=request,
                req=MagicMock(attempt_id="a1", feedback=None, session_id=None),
                user_id="user1",
                service=AsyncMock(),
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_regenerate_query_no_session_returns_401(self):
        from app.api.v1.query import regenerate_query

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await regenerate_query(
                request=request,
                req=MagicMock(attempt_id="a1", session_id=None),
                user_id="user1",
                service=AsyncMock(),
            )
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_regenerate_query_wrong_permission_returns_403(self):
        from app.api.v1.query import regenerate_query

        request = _make_request_with_permissions(["query.history.view"])
        with pytest.raises(HTTPException) as exc:
            await regenerate_query(
                request=request,
                req=MagicMock(attempt_id="a1", session_id=None),
                user_id="user1",
                service=AsyncMock(),
            )
        assert exc.value.status_code == 403


# ── History Endpoints (history.py) ──────────────────────────────────────────


class TestHistoryPermissionGates:
    """All /history endpoints require query.history.view."""

    @pytest.mark.asyncio
    async def test_list_history_no_session_returns_401(self):
        from app.api.v1.history import list_history

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await list_history(
                request=request,
                cursor=None,
                limit=100,
                user_id="user1",
                service=AsyncMock(),
            )
        assert exc.value.status_code == 401
        detail = exc.value.detail
        assert detail["error"] == "unauthorized"
        assert detail["message_key"] == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_list_history_wrong_permission_returns_403(self):
        from app.api.v1.history import list_history

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await list_history(
                request=request,
                cursor=None,
                limit=100,
                user_id="user1",
                service=AsyncMock(),
            )
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert detail["error"] == "forbidden"
        assert detail["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_get_history_entry_no_session_returns_401(self):
        from app.api.v1.history import get_history_entry

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await get_history_entry(
                request=request,
                query_id=uuid.uuid4(),
                user_id="user1",
                service=AsyncMock(),
            )
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_history_entry_wrong_permission_returns_403(self):
        from app.api.v1.history import get_history_entry

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await get_history_entry(
                request=request,
                query_id=uuid.uuid4(),
                user_id="user1",
                service=AsyncMock(),
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_history_entry_no_session_returns_401(self):
        from app.api.v1.history import delete_history_entry

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await delete_history_entry(
                request=request,
                query_id=uuid.uuid4(),
                user_id="user1",
                service=AsyncMock(),
            )
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_history_entry_wrong_permission_returns_403(self):
        from app.api.v1.history import delete_history_entry

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await delete_history_entry(
                request=request,
                query_id=uuid.uuid4(),
                user_id="user1",
                service=AsyncMock(),
            )
        assert exc.value.status_code == 403


# ── Sanitization ──────────────────────────────────────────────────────────


class TestPermissionGateErrorSanitization:
    """403/401 responses must not leak internals."""

    @pytest.mark.asyncio
    async def test_403_does_not_expose_permission_internals(self):
        from app.api.v1.admin_connections import list_connections

        request = _make_request_with_permissions(["query.submit"])
        with pytest.raises(HTTPException) as exc:
            await list_connections(request=request, service=AsyncMock())
        detail = exc.value.detail
        assert "admin.connections.manage" not in str(detail).lower()
        assert "query.submit" not in str(detail).lower()
        assert set(detail.keys()) == {"error", "message_key"}

    @pytest.mark.asyncio
    async def test_401_does_not_expose_user_internals(self):
        from app.api.v1.query import submit_question

        request = _make_request_with_permissions(None)
        with pytest.raises(HTTPException) as exc:
            await submit_question(
                request=request,
                req=MagicMock(question="test", connection_id="conn1", session_id=None),
                user_id="user1",
                db=AsyncMock(),
                redis=AsyncMock(),
            )
        detail = exc.value.detail
        assert "550e8400" not in str(detail)
        assert set(detail.keys()) == {"error", "message_key"}
