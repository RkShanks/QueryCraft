"""TDD tests for role CRUD endpoints (T-671).

Tests:
- GET /admin/roles — requires admin.roles.manage, returns list with group_mappings
- POST /admin/roles — requires admin.roles.manage, validates permissions,
  rejects duplicate name (409), rejects duplicate priority (409),
  creates role with group_mappings and connection_policies
- GET /admin/roles/{id} — requires admin.roles.manage, returns full detail
- PUT /admin/roles/{id} — requires admin.roles.manage, validates permissions,
  rejects duplicate name/priority (409), protects built-in role core fields (403)
- DELETE /admin/roles/{id} — requires admin.roles.manage,
  rejects built-in role deletion (403)
- All errors sanitized: no raw UUIDs, DB errors, stack traces, permission internals.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.db.models.role import Role
from app.schemas.roles import RoleCreate, RoleUpdate

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


def _make_role(
    role_id=None,
    name="Analyst",
    description="Read-only analyst",
    priority=10,
    permissions=None,
    is_builtin=False,
):
    role = MagicMock(spec=Role)
    role.id = role_id or uuid.uuid4()
    role.name = name
    role.description = description
    role.priority = priority
    role.permissions = permissions or ["query.submit", "query.history.view"]
    role.is_builtin = is_builtin
    role.created_at = datetime.now(UTC)
    role.updated_at = datetime.now(UTC)
    return role


def _make_builtin_role():
    return _make_role(
        name="Built-in Admin",
        description="System administrator",
        priority=0,
        permissions=[
            "query.submit",
            "query.history.view",
            "admin.connections.manage",
            "admin.roles.manage",
            "admin.sso.manage",
            "admin.audit.verify",
        ],
        is_builtin=True,
    )


# ── Permission Enforcement ─────────────────────────────────────────────────


class TestPermissionEnforcement:
    """All role admin endpoints require admin.roles.manage permission."""

    def _make_app(self, session_data: dict | None):
        from fastapi.responses import JSONResponse
        from starlette.middleware.base import BaseHTTPMiddleware

        from app.api.v1.admin_roles import router

        class SessionInjectionMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                request.state.session = session_data
                return await call_next(request)

        async def _http_exc_handler(request, exc):
            if isinstance(exc.detail, dict):
                return JSONResponse(status_code=exc.status_code, content=exc.detail)
            return JSONResponse(status_code=exc.status_code, content={"error": "error", "message_key": str(exc.detail)})

        app = FastAPI()
        app.add_middleware(SessionInjectionMiddleware)
        app.add_exception_handler(HTTPException, _http_exc_handler)
        app.include_router(router, prefix="/api/v1")
        return app

    @pytest.mark.asyncio
    async def test_list_roles_requires_admin_roles_manage(self):
        app = self._make_app({"role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "permissions": ["query.submit"]})
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/roles")
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "forbidden"
        assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_create_role_requires_admin_roles_manage(self):
        app = self._make_app({"role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "permissions": ["query.submit"]})
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/roles",
                json={"name": "Test", "priority": 10, "permissions": []},
            )
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "forbidden"
        assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_get_role_requires_admin_roles_manage(self):
        app = self._make_app({"role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "permissions": ["query.submit"]})
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/admin/roles/{uuid.uuid4()}")
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "forbidden"
        assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_update_role_requires_admin_roles_manage(self):
        app = self._make_app({"role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "permissions": ["query.submit"]})
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(f"/api/v1/admin/roles/{uuid.uuid4()}", json={})
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "forbidden"
        assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_delete_role_requires_admin_roles_manage(self):
        app = self._make_app({"role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "permissions": ["query.submit"]})
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/api/v1/admin/roles/{uuid.uuid4()}")
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "forbidden"
        assert data["message_key"] == "error.forbidden"


# ── GET /admin/roles ───────────────────────────────────────────────────────


class TestListRoles:
    """GET /admin/roles returns roles with group_mappings and policy counts."""

    @pytest.mark.asyncio
    async def test_list_returns_roles(self):
        from app.api.v1.admin_roles import list_roles

        role1 = _make_role(name="Analyst", priority=10)
        role2 = _make_role(name="Admin", priority=5)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([role1, role2]),  # roles query
                FakeResult([]),  # group mappings query
                FakeResult([]),  # connection policies count
            ]
        )

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        result = await list_roles(_session=request.state.session, db=mock_db)

        roles = result["roles"]
        assert len(roles) == 2
        assert roles[0]["name"] == "Analyst"
        assert roles[1]["name"] == "Admin"

    @pytest.mark.asyncio
    async def test_list_empty_returns_empty_roles(self):
        from app.api.v1.admin_roles import list_roles

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),  # roles query
                FakeResult([]),  # group mappings query
                FakeResult([]),  # connection policies count
            ]
        )

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        result = await list_roles(_session=request.state.session, db=mock_db)
        assert result["roles"] == []

    @pytest.mark.asyncio
    async def test_list_includes_group_mappings(self):
        from app.api.v1.admin_roles import list_roles

        role = _make_role(name="Analyst", priority=10)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([role]),  # roles query
                FakeResult([]),  # group mappings query
                FakeResult([]),  # connection policies count
            ]
        )

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        result = await list_roles(_session=request.state.session, db=mock_db)

        roles = result["roles"]
        assert len(roles) == 1
        assert "group_mappings" in roles[0]

    @pytest.mark.asyncio
    async def test_list_includes_connection_policy_count(self):
        from app.api.v1.admin_roles import list_roles

        role = _make_role(name="Analyst", priority=10)

        # Build a tuple-like count row for the aggregate query
        count_row = MagicMock()
        count_row.__getitem__ = lambda self, i: [role.id, 1][i]
        count_row.__len__ = lambda self: 2

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([role]),  # roles query
                FakeResult([]),  # group mappings query
                FakeResult([count_row]),  # connection policies count
            ]
        )

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        result = await list_roles(_session=request.state.session, db=mock_db)

        roles = result["roles"]
        assert roles[0]["connection_policy_count"] == 1


# ── POST /admin/roles ──────────────────────────────────────────────────────


class TestCreateRole:
    """POST /admin/roles creates role with validation."""

    @pytest.mark.asyncio
    async def test_create_role_success(self):
        from app.api.v1.admin_roles import create_role

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),  # duplicate name check
                FakeResult([]),  # duplicate priority check
                FakeResult([MagicMock()]),  # RETURNING result
            ]
        )
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.add = MagicMock()

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
            "username": "admin",
        }

        body = RoleCreate(
            name="Analyst",
            description="Read-only",
            priority=10,
            permissions=["query.submit", "query.history.view"],
        )

        result = await create_role(request=request, body=body, db=mock_db)

        assert result["name"] == "Analyst"
        assert result["priority"] == 10
        assert result["permissions"] == ["query.submit", "query.history.view"]

    @pytest.mark.asyncio
    async def test_create_duplicate_name_returns_409(self):
        from app.api.v1.admin_roles import create_role

        existing = _make_role(name="Analyst", priority=10)
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([existing]))

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = RoleCreate(
            name="Analyst",
            priority=20,
            permissions=["query.submit"],
        )

        with pytest.raises(HTTPException) as exc:
            await create_role(request=request, body=body, db=mock_db)
        assert exc.value.status_code == 409
        detail = exc.value.detail
        assert detail["error"] == "conflict"
        assert "duplicateName" in detail["message_key"] or "duplicate" in detail["message_key"].lower()
        assert "uuid" not in str(detail).lower()

    @pytest.mark.asyncio
    async def test_create_duplicate_priority_returns_409(self):
        from app.api.v1.admin_roles import create_role

        existing = _make_role(name="Admin", priority=10)
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),  # no duplicate name
                FakeResult([existing]),  # duplicate priority
            ]
        )

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = RoleCreate(
            name="New Role",
            priority=10,
            permissions=["query.submit"],
        )

        with pytest.raises(HTTPException) as exc:
            await create_role(request=request, body=body, db=mock_db)
        assert exc.value.status_code == 409
        detail = exc.value.detail
        assert detail["error"] == "conflict"
        assert "duplicatePriority" in detail["message_key"] or "duplicate" in detail["message_key"].lower()

    @pytest.mark.asyncio
    async def test_create_invalid_permission_returns_422(self):
        from app.api.v1.admin_roles import create_role

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([]))

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = RoleCreate(
            name="Bad Role",
            priority=10,
            permissions=["invalid.permission"],
        )

        with pytest.raises(HTTPException) as exc:
            await create_role(request=request, body=body, db=mock_db)
        assert exc.value.status_code == 422
        detail = exc.value.detail
        assert detail["error"] == "validation"
        assert "permission" in detail["message_key"].lower() or "invalid" in detail["message_key"].lower()

    @pytest.mark.asyncio
    async def test_create_error_sanitized(self):
        from app.api.v1.admin_roles import create_role

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB error: uuid=550e8400-e29b-41d4-a716-446655440000"))

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = RoleCreate(
            name="Test",
            priority=10,
            permissions=["query.submit"],
        )

        with pytest.raises(HTTPException) as exc:
            await create_role(request=request, body=body, db=mock_db)
        assert exc.value.status_code in (400, 422, 500)
        detail_str = str(exc.value.detail)
        assert "550e8400" not in detail_str
        assert "DB error" not in detail_str


# ── GET /admin/roles/{id} ────────────────────────────────────────────────


class TestGetRole:
    """GET /admin/roles/{id} returns full role detail."""

    @pytest.mark.asyncio
    async def test_get_role_success(self):
        from app.api.v1.admin_roles import get_role

        role = _make_role(name="Analyst", priority=10)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult(role),  # role query
                FakeResult([]),  # group mappings
                FakeResult([]),  # connection policies
            ]
        )

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        result = await get_role(_session=request.state.session, role_id=str(role.id), db=mock_db)

        assert result["id"] == str(role.id)
        assert result["name"] == "Analyst"
        assert "connection_policies" in result

    @pytest.mark.asyncio
    async def test_get_role_not_found_returns_404(self):
        from app.api.v1.admin_roles import get_role

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult(None))

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        with pytest.raises(HTTPException) as exc:
            await get_role(_session=request.state.session, role_id=str(uuid.uuid4()), db=mock_db)
        assert exc.value.status_code == 404
        detail = exc.value.detail
        assert detail["error"] == "not_found"
        assert "uuid" not in str(detail).lower()


# ── PUT /admin/roles/{id} ────────────────────────────────────────────────


class TestUpdateRole:
    """PUT /admin/roles/{id} updates role with validation and built-in protection."""

    @pytest.mark.asyncio
    async def test_update_role_success(self):
        from app.api.v1.admin_roles import update_role

        role = _make_role(name="Analyst", priority=10)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult(role),  # service.get_by_id
                FakeResult([]),  # no duplicate name
                FakeResult(role),  # repo.update internal get_by_id
                FakeResult([MagicMock()]),  # db.refresh
            ]
        )
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
            "username": "admin",
        }

        body = RoleUpdate(name="Updated Analyst", description="Updated desc")

        result = await update_role(request=request, role_id=str(role.id), body=body, db=mock_db)

        assert result["name"] == "Updated Analyst"
        assert result["description"] == "Updated desc"

    @pytest.mark.asyncio
    async def test_update_builtin_role_name_returns_403(self):
        from app.api.v1.admin_roles import update_role

        role = _make_builtin_role()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult(role))
        mock_db.commit = AsyncMock()

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = RoleUpdate(name="Hacked Admin")

        with pytest.raises(HTTPException) as exc:
            await update_role(request=request, role_id=str(role.id), body=body, db=mock_db)
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert detail["error"] == "forbidden"
        assert detail["message_key"] == "error.builtinRoleProtected"
        assert "uuid" not in str(detail).lower()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_builtin_role_permissions_returns_403(self):
        from app.api.v1.admin_roles import update_role

        role = _make_builtin_role()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult(role))
        mock_db.commit = AsyncMock()

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = RoleUpdate(permissions=[])

        with pytest.raises(HTTPException) as exc:
            await update_role(request=request, role_id=str(role.id), body=body, db=mock_db)
        assert exc.value.status_code == 403
        assert exc.value.detail["message_key"] == "error.builtinRoleProtected"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_builtin_role_priority_returns_403(self):
        from app.api.v1.admin_roles import update_role

        role = _make_builtin_role()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult(role))
        mock_db.commit = AsyncMock()

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = RoleUpdate(priority=99)

        with pytest.raises(HTTPException) as exc:
            await update_role(request=request, role_id=str(role.id), body=body, db=mock_db)
        assert exc.value.status_code == 403
        assert exc.value.detail["message_key"] == "error.builtinRoleProtected"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_builtin_role_description_allowed(self):
        from app.api.v1.admin_roles import update_role

        role = _make_builtin_role()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult(role),  # service.get_by_id
                FakeResult(role),  # repo.update internal get_by_id
            ]
        )
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
            "username": "admin",
        }

        body = RoleUpdate(description="Updated description")

        result = await update_role(request=request, role_id=str(role.id), body=body, db=mock_db)
        assert result["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_update_duplicate_name_returns_409(self):
        from app.api.v1.admin_roles import update_role

        role = _make_role(name="Analyst", priority=10)
        other = _make_role(name="Existing", priority=20)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult(role),  # service.get_by_id
                FakeResult([other]),  # duplicate name check
            ]
        )

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = RoleUpdate(name="Existing")

        with pytest.raises(HTTPException) as exc:
            await update_role(request=request, role_id=str(role.id), body=body, db=mock_db)
        assert exc.value.status_code == 409
        detail = exc.value.detail
        assert detail["error"] == "conflict"
        assert "duplicateName" in detail["message_key"] or "duplicate" in detail["message_key"].lower()

    @pytest.mark.asyncio
    async def test_update_duplicate_priority_returns_409(self):
        from app.api.v1.admin_roles import update_role

        role = _make_role(name="Analyst", priority=10)
        other = _make_role(name="Existing", priority=20)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult(role),  # service.get_by_id
                FakeResult([other]),  # duplicate priority
            ]
        )

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = RoleUpdate(priority=20)

        with pytest.raises(HTTPException) as exc:
            await update_role(request=request, role_id=str(role.id), body=body, db=mock_db)
        assert exc.value.status_code == 409
        detail = exc.value.detail
        assert detail["error"] == "conflict"
        assert "duplicatePriority" in detail["message_key"] or "duplicate" in detail["message_key"].lower()

    @pytest.mark.asyncio
    async def test_update_invalid_permission_returns_422(self):
        from app.api.v1.admin_roles import update_role

        role = _make_role(name="Analyst", priority=10)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult(role))

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = RoleUpdate(permissions=["invalid.permission"])

        with pytest.raises(HTTPException) as exc:
            await update_role(request=request, role_id=str(role.id), body=body, db=mock_db)
        assert exc.value.status_code == 422
        detail = exc.value.detail
        assert detail["error"] == "validation"

    @pytest.mark.asyncio
    async def test_update_not_found_returns_404(self):
        from app.api.v1.admin_roles import update_role

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult(None))

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = RoleUpdate(name="Updated")

        with pytest.raises(HTTPException) as exc:
            await update_role(request=request, role_id=str(uuid.uuid4()), body=body, db=mock_db)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_error_sanitized(self):
        from app.api.v1.admin_roles import update_role

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB error: uuid=550e8400-e29b-41d4-a716-446655440000"))

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = RoleUpdate(name="Updated")

        with pytest.raises(HTTPException) as exc:
            await update_role(request=request, role_id=str(uuid.uuid4()), body=body, db=mock_db)
        detail_str = str(exc.value.detail)
        assert "550e8400" not in detail_str
        assert "DB error" not in detail_str


# ── DELETE /admin/roles/{id} ───────────────────────────────────────────────


class TestDeleteRole:
    """DELETE /admin/roles/{id} removes role, protects built-in."""

    @pytest.mark.asyncio
    async def test_delete_role_success(self):
        from app.api.v1.admin_roles import delete_role

        role = _make_role(name="Analyst", priority=10)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult(role))
        mock_db.commit = AsyncMock()

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
            "username": "admin",
        }

        result = await delete_role(request=request, role_id=str(role.id), db=mock_db)
        assert result is None
        mock_db.delete.assert_called_once_with(role)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_builtin_role_returns_403(self):
        from app.api.v1.admin_roles import delete_role

        role = _make_builtin_role()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult(role))
        mock_db.commit = AsyncMock()

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        with pytest.raises(HTTPException) as exc:
            await delete_role(request=request, role_id=str(role.id), db=mock_db)
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert detail["message_key"] == "error.builtinRoleProtected"
        assert "uuid" not in str(detail).lower()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_not_found_returns_404(self):
        from app.api.v1.admin_roles import delete_role

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult(None))

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        with pytest.raises(HTTPException) as exc:
            await delete_role(request=request, role_id=str(uuid.uuid4()), db=mock_db)
        assert exc.value.status_code == 404
        detail = exc.value.detail
        assert detail["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_delete_error_sanitized(self):
        from app.api.v1.admin_roles import delete_role

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB error: uuid=550e8400-e29b-41d4-a716-446655440000"))

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        with pytest.raises(HTTPException) as exc:
            await delete_role(request=request, role_id=str(uuid.uuid4()), db=mock_db)
        detail_str = str(exc.value.detail)
        assert "550e8400" not in detail_str
        assert "DB error" not in detail_str


# ── Validation Helpers ───────────────────────────────────────────────────


class TestPermissionValidation:
    """Permission values must be from the fixed allowed set."""

    def test_all_valid_permissions_accepted(self):
        from app.api.v1.admin_roles import _validate_permissions

        valid = [
            "query.submit",
            "query.history.view",
            "admin.connections.manage",
            "admin.roles.manage",
            "admin.sso.manage",
            "admin.audit.verify",
        ]
        # Should not raise
        _validate_permissions(valid)

    def test_invalid_permission_rejected(self):
        from app.api.v1.admin_roles import _validate_permissions

        with pytest.raises(ValueError) as exc:
            _validate_permissions(["query.submit", "invalid.permission"])
        assert "invalid.permission" in str(exc.value)

    def test_empty_permissions_allowed(self):
        from app.api.v1.admin_roles import _validate_permissions

        _validate_permissions([])

    def test_none_permissions_allowed(self):
        from app.api.v1.admin_roles import _validate_permissions

        _validate_permissions(None)
