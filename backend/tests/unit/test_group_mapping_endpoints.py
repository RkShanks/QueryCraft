"""TDD tests for SSO group mapping endpoints (T-676).

Tests:
- GET /admin/sso/group-mappings — requires admin.roles.manage, returns list
- POST /admin/sso/group-mappings — requires admin.roles.manage,
  validates role exists, rejects duplicate group value (409)
- DELETE /admin/sso/group-mappings/{id} — requires admin.roles.manage,
  returns 404 if mapping not found
- Permission: endpoints use ``admin.roles.manage`` (NOT admin.sso.manage).
- All errors sanitized: no raw UUIDs, DB errors, stack traces, SSO internals.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.db.models.role import Role
from app.db.models.sso_group_mapping import SsoGroupMapping
from app.schemas.group_mapping import GroupMappingCreate

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


def _make_role(role_id=None, name="Analyst"):
    role = MagicMock(spec=Role)
    role.id = role_id or uuid.uuid4()
    role.name = name
    return role


def _make_mapping(mapping_id=None, group_value="analysts", role_id=None):
    mapping = MagicMock(spec=SsoGroupMapping)
    mapping.id = mapping_id or uuid.uuid4()
    mapping.sso_group_value = group_value
    mapping.role_id = role_id or uuid.uuid4()
    mapping.created_at = datetime.now(UTC)
    return mapping


# ── Permission Enforcement ─────────────────────────────────────────────────


class TestPermissionEnforcement:
    """All group mapping endpoints require admin.roles.manage permission."""

    @pytest.mark.asyncio
    async def test_list_mappings_requires_admin_roles_manage(self):
        from app.api.v1.admin_sso import list_group_mappings

        request = MagicMock()
        request.state.session = {"role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "permissions": ["query.submit"]}

        with pytest.raises(HTTPException) as exc:
            await list_group_mappings(request=request, db=AsyncMock())
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert detail["error"] == "forbidden"
        assert detail["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_list_mappings_rejects_admin_sso_manage(self):
        """admin.sso.manage does NOT grant access to group mappings."""
        from app.api.v1.admin_sso import list_group_mappings

        request = MagicMock()
        request.state.session = {"role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "permissions": ["admin.sso.manage"]}

        with pytest.raises(HTTPException) as exc:
            await list_group_mappings(request=request, db=AsyncMock())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_create_mapping_requires_admin_roles_manage(self):
        from app.api.v1.admin_sso import create_group_mapping

        request = MagicMock()
        request.state.session = {"role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "permissions": ["query.submit"]}

        with pytest.raises(HTTPException) as exc:
            await create_group_mapping(
                request=request,
                body=GroupMappingCreate(sso_group_value="analysts", role_id=str(uuid.uuid4())),
                db=AsyncMock(),
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_mapping_requires_admin_roles_manage(self):
        from app.api.v1.admin_sso import delete_group_mapping

        request = MagicMock()
        request.state.session = {"role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "permissions": ["query.submit"]}

        with pytest.raises(HTTPException) as exc:
            await delete_group_mapping(
                request=request,
                mapping_id=str(uuid.uuid4()),
                db=AsyncMock(),
            )
        assert exc.value.status_code == 403


# ── GET /admin/sso/group-mappings ──────────────────────────────────────────


class TestListGroupMappings:
    """GET /admin/sso/group-mappings returns all mappings with role names."""

    @pytest.mark.asyncio
    async def test_list_returns_mappings(self):
        from app.api.v1.admin_sso import list_group_mappings

        role = _make_role(name="Analyst")
        mapping = _make_mapping(role_id=role.id)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([mapping]),  # mappings query
                FakeResult([role]),  # roles query for name resolution
            ]
        )

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        result = await list_group_mappings(request=request, db=mock_db)

        mappings = result["mappings"]
        assert len(mappings) == 1
        assert mappings[0]["sso_group_value"] == "analysts"
        assert mappings[0]["role_name"] == "Analyst"
        assert "id" in mappings[0]
        assert "role_id" in mappings[0]
        assert "created_at" in mappings[0]

    @pytest.mark.asyncio
    async def test_list_empty_returns_empty_mappings(self):
        from app.api.v1.admin_sso import list_group_mappings

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),  # mappings query
                FakeResult([]),  # roles query
            ]
        )

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        result = await list_group_mappings(request=request, db=mock_db)
        assert result["mappings"] == []

    @pytest.mark.asyncio
    async def test_list_error_sanitized(self):
        from app.api.v1.admin_sso import list_group_mappings

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB leak: secret_table=group_mappings"))

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        with pytest.raises(HTTPException) as exc:
            await list_group_mappings(request=request, db=mock_db)
        assert exc.value.status_code == 500
        detail_str = str(exc.value.detail)
        assert "secret_table" not in detail_str
        assert "group_mappings" not in detail_str
        assert "DB leak" not in detail_str


# ── POST /admin/sso/group-mappings ─────────────────────────────────────────


class TestCreateGroupMapping:
    """POST /admin/sso/group-mappings creates mapping with validation."""

    @pytest.mark.asyncio
    async def test_create_success(self):
        from app.api.v1.admin_sso import create_group_mapping

        role = _make_role(name="Analyst")
        mapping = _make_mapping(role_id=role.id)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),  # duplicate group check
                FakeResult([role]),  # role existence check
                FakeResult([mapping]),  # RETURNING result
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

        body = GroupMappingCreate(sso_group_value="analysts", role_id=str(role.id))

        result = await create_group_mapping(request=request, body=body, db=mock_db)

        assert result["sso_group_value"] == "analysts"
        assert result["role_id"] == str(role.id)
        assert result["role_name"] == "Analyst"
        assert "id" in result
        assert "created_at" in result

    @pytest.mark.asyncio
    async def test_create_duplicate_group_returns_409(self):
        from app.api.v1.admin_sso import create_group_mapping

        existing = _make_mapping(group_value="analysts")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([existing]))

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = GroupMappingCreate(sso_group_value="analysts", role_id=str(uuid.uuid4()))

        with pytest.raises(HTTPException) as exc:
            await create_group_mapping(request=request, body=body, db=mock_db)
        assert exc.value.status_code == 409
        detail = exc.value.detail
        assert detail["error"] == "conflict"
        assert "duplicateGroupMapping" in detail["message_key"]
        # No raw UUIDs or internal details leaked
        assert "uuid" not in str(detail).lower()

    @pytest.mark.asyncio
    async def test_create_missing_role_returns_404(self):
        from app.api.v1.admin_sso import create_group_mapping

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),  # duplicate group check
                FakeResult([]),  # role existence check — not found
            ]
        )

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = GroupMappingCreate(sso_group_value="analysts", role_id=str(uuid.uuid4()))

        with pytest.raises(HTTPException) as exc:
            await create_group_mapping(request=request, body=body, db=mock_db)
        assert exc.value.status_code == 404
        detail = exc.value.detail
        assert detail["error"] == "not_found"
        assert detail["message_key"] == "error.notFound"
        assert "uuid" not in str(detail).lower()

    @pytest.mark.asyncio
    async def test_create_error_sanitized(self):
        from app.api.v1.admin_sso import create_group_mapping

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB error: host=secret-idp.internal"))

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = GroupMappingCreate(sso_group_value="analysts", role_id=str(uuid.uuid4()))

        with pytest.raises(HTTPException) as exc:
            await create_group_mapping(request=request, body=body, db=mock_db)
        detail_str = str(exc.value.detail)
        assert "secret-idp.internal" not in detail_str
        assert "DB error" not in detail_str

    @pytest.mark.asyncio
    async def test_create_invalid_role_id_returns_sanitized_404(self):
        """Invalid role_id UUID must not leak raw input in response."""
        from app.api.v1.admin_sso import create_group_mapping

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        body = GroupMappingCreate(sso_group_value="analysts", role_id="not-a-uuid")

        with pytest.raises(HTTPException) as exc:
            await create_group_mapping(request=request, body=body, db=AsyncMock())
        assert exc.value.status_code == 404
        detail = exc.value.detail
        assert detail["error"] == "not_found"
        assert detail["message_key"] == "error.notFound"
        assert "not-a-uuid" not in str(detail).lower()


# ── DELETE /admin/sso/group-mappings/{id} ──────────────────────────────────


class TestDeleteGroupMapping:
    """DELETE /admin/sso/group-mappings/{id} removes mapping."""

    @pytest.mark.asyncio
    async def test_delete_existing_returns_204(self):
        from app.api.v1.admin_sso import delete_group_mapping

        mapping = _make_mapping()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([mapping]))
        mock_db.commit = AsyncMock()

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
            "username": "admin",
        }

        result = await delete_group_mapping(
            request=request,
            mapping_id=str(mapping.id),
            db=mock_db,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_not_found_returns_404(self):
        from app.api.v1.admin_sso import delete_group_mapping

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([]))

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        with pytest.raises(HTTPException) as exc:
            await delete_group_mapping(
                request=request,
                mapping_id=str(uuid.uuid4()),
                db=mock_db,
            )
        assert exc.value.status_code == 404
        detail = exc.value.detail
        assert detail["error"] == "not_found"
        assert detail["message_key"] == "error.notFound"
        assert "uuid" not in str(detail).lower()

    @pytest.mark.asyncio
    async def test_delete_error_sanitized(self):
        from app.api.v1.admin_sso import delete_group_mapping

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB error: secret table leak"))

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        with pytest.raises(HTTPException) as exc:
            await delete_group_mapping(
                request=request,
                mapping_id=str(uuid.uuid4()),
                db=mock_db,
            )
        detail_str = str(exc.value.detail)
        assert "secret table leak" not in detail_str

    @pytest.mark.asyncio
    async def test_delete_invalid_mapping_id_returns_sanitized_404(self):
        """Invalid mapping_id UUID must not leak raw input in response."""
        from app.api.v1.admin_sso import delete_group_mapping

        request = MagicMock()
        request.state.session = {
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "permissions": ["admin.roles.manage"],
        }

        with pytest.raises(HTTPException) as exc:
            await delete_group_mapping(
                request=request,
                mapping_id="not-a-uuid",
                db=AsyncMock(),
            )
        assert exc.value.status_code == 404
        detail = exc.value.detail
        assert detail["error"] == "not_found"
        assert detail["message_key"] == "error.notFound"
        assert "not-a-uuid" not in str(detail).lower()


# ── Route-Level Tests ───────────────────────────────────────────────────────


class TestRouteLevelStatusCodes:
    """Verify router-level status codes via actual FastAPI app wiring."""

    def _build_app(self, session=None):
        """Build isolated FastAPI app with router, exception handler, and optional session."""
        from fastapi.responses import JSONResponse

        from app.api.v1.admin_sso import router
        from app.core.dependencies import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        async def override_db():
            return AsyncMock()

        app.dependency_overrides[get_db] = override_db

        @app.exception_handler(HTTPException)
        async def _http_exc_handler(request, exc):
            if isinstance(exc.detail, dict):
                return JSONResponse(status_code=exc.status_code, content=exc.detail)
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": "error", "message_key": str(exc.detail)},
            )

        if session is not None:
            from starlette.middleware.base import BaseHTTPMiddleware

            class InjectSessionMiddleware(BaseHTTPMiddleware):
                async def dispatch(self, request, call_next):
                    _sess = dict(session)
                    if "role_id" not in _sess:
                        _sess["role_id"] = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
                    request.state.session = _sess
                    return await call_next(request)

            app.add_middleware(InjectSessionMiddleware)

        return app

    @pytest.mark.asyncio
    async def test_get_returns_200(self):
        app = self._build_app(session={"permissions": ["admin.roles.manage"]})

        from app.core.dependencies import get_db

        role = _make_role(name="Analyst")
        mapping = _make_mapping(role_id=role.id)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([mapping]),
                FakeResult([role]),
            ]
        )
        app.dependency_overrides[get_db] = lambda: mock_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/admin/sso/group-mappings",
                headers={"origin": "http://test"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "mappings" in data
        assert len(data["mappings"]) == 1

    @pytest.mark.asyncio
    async def test_post_returns_201(self):
        app = self._build_app(session={"permissions": ["admin.roles.manage"]})

        from app.core.dependencies import get_db

        role = _make_role(name="Analyst")
        mapping = _make_mapping(role_id=role.id)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),  # no duplicate
                FakeResult([role]),  # role exists
                FakeResult([mapping]),  # insert RETURNING
            ]
        )
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.add = MagicMock()

        app.dependency_overrides[get_db] = lambda: mock_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/sso/group-mappings",
                json={"sso_group_value": "analysts", "role_id": str(role.id)},
                headers={"origin": "http://test"},
            )
        assert response.status_code == 201
        data = response.json()
        assert data["sso_group_value"] == "analysts"
        assert data["role_name"] == "Analyst"

    @pytest.mark.asyncio
    async def test_delete_returns_204(self):
        app = self._build_app(session={"permissions": ["admin.roles.manage"]})

        from app.core.dependencies import get_db

        mapping = _make_mapping()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([mapping]))
        mock_db.commit = AsyncMock()

        app.dependency_overrides[get_db] = lambda: mock_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/admin/sso/group-mappings/{mapping.id}",
                headers={"origin": "http://test"},
            )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_post_returns_401_without_session(self):
        app = self._build_app()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/sso/group-mappings",
                json={"sso_group_value": "analysts", "role_id": str(uuid.uuid4())},
                headers={"origin": "http://test"},
            )
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "unauthorized"
        assert data["message_key"] == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_post_returns_403_with_wrong_permission(self):
        app = self._build_app(session={"permissions": ["admin.sso.manage"]})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/sso/group-mappings",
                json={"sso_group_value": "analysts", "role_id": str(uuid.uuid4())},
                headers={"origin": "http://test"},
            )
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "forbidden"
        assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_post_duplicate_returns_409(self):
        app = self._build_app(session={"permissions": ["admin.roles.manage"]})

        from app.core.dependencies import get_db

        existing = _make_mapping(group_value="analysts")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([existing]))

        app.dependency_overrides[get_db] = lambda: mock_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/sso/group-mappings",
                json={"sso_group_value": "analysts", "role_id": str(uuid.uuid4())},
                headers={"origin": "http://test"},
            )
        assert response.status_code == 409
        data = response.json()
        assert data["error"] == "conflict"
        assert "duplicateGroupMapping" in data["message_key"]

    @pytest.mark.asyncio
    async def test_post_missing_role_returns_404(self):
        app = self._build_app(session={"permissions": ["admin.roles.manage"]})

        from app.core.dependencies import get_db

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),  # no duplicate
                FakeResult([]),  # role not found
            ]
        )

        app.dependency_overrides[get_db] = lambda: mock_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/sso/group-mappings",
                json={"sso_group_value": "analysts", "role_id": str(uuid.uuid4())},
                headers={"origin": "http://test"},
            )
        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "not_found"
        assert data["message_key"] == "error.notFound"

    @pytest.mark.asyncio
    async def test_delete_not_found_returns_404(self):
        app = self._build_app(session={"permissions": ["admin.roles.manage"]})

        from app.core.dependencies import get_db

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([]))

        app.dependency_overrides[get_db] = lambda: mock_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/admin/sso/group-mappings/{uuid.uuid4()}",
                headers={"origin": "http://test"},
            )
        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "not_found"
        assert data["message_key"] == "error.notFound"

    @pytest.mark.asyncio
    async def test_post_invalid_role_id_returns_sanitized_404(self):
        app = self._build_app(session={"permissions": ["admin.roles.manage"]})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/sso/group-mappings",
                json={"sso_group_value": "analysts", "role_id": "not-a-uuid"},
                headers={"origin": "http://test"},
            )
        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "not_found"
        assert data["message_key"] == "error.notFound"
        assert "not-a-uuid" not in str(data).lower()

    @pytest.mark.asyncio
    async def test_delete_invalid_mapping_id_returns_sanitized_404(self):
        app = self._build_app(session={"permissions": ["admin.roles.manage"]})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                "/api/v1/admin/sso/group-mappings/not-a-uuid",
                headers={"origin": "http://test"},
            )
        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "not_found"
        assert data["message_key"] == "error.notFound"
        assert "not-a-uuid" not in str(data).lower()

    @pytest.mark.asyncio
    async def test_router_registered_in_main_app(self):
        """Verify /api/v1/admin/sso/group-mappings path exists in main app."""
        from app.main import create_app

        app = create_app()
        paths = [route.path for route in app.routes if hasattr(route, "path")]
        assert "/api/v1/admin/sso/group-mappings" in paths
