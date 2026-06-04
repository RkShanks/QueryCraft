"""TDD tests for RBAC audit logging (T-683).

Covers:
- Role create/update/delete → role.create / role.update / role.delete
- Group mapping create/delete → role.mapping.change
- Built-in role protection denial → access.denied
- Audit context redaction: no credentials, passwords, tokens, role internals
- Audit atomicity: mutation must not commit if required audit write fails
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import BuiltinProtectedError
from app.db.models.enums import AuditActionType
from app.db.models.role import Role
from app.repositories.role_repository import RoleRepository
from app.services.role_service import RoleService

# ── Helpers ─────────────────────────────────────────────────────────────────


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
    return role


class _FakeMapping:
    """Fake SsoGroupMapping that accepts keyword args like the ORM model."""

    def __init__(self, *, sso_group_value=None, role_id=None, id=None, **kwargs):
        self.id = id or uuid.uuid4()
        self.sso_group_value = sso_group_value or "analysts"
        self.role_id = role_id or uuid.uuid4()
        self.created_at = None


def _make_mapping(mapping_id=None, group_value="analysts", role_id=None):
    return _FakeMapping(id=mapping_id, sso_group_value=group_value, role_id=role_id)


class FakeResult:
    """Mock SQLAlchemy result."""

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


# ── RoleService Audit Logging ─────────────────────────────────────────────


@pytest.mark.asyncio
class TestRoleServiceAuditLogging:
    """AuditService.log is called during role CRUD operations."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def mock_repo(self, mock_db):
        repo = MagicMock(spec=RoleRepository)
        repo._session = mock_db
        return repo

    @pytest.fixture
    def service(self, mock_repo):
        return RoleService(mock_repo)

    async def test_create_role_logs_role_create(self, service, mock_repo, mock_db):
        """Successful role creation logs role.create audit event."""
        role = _make_role(name="Auditor", priority=20)
        mock_repo.get_by_name = AsyncMock(return_value=None)
        mock_repo.get_by_priority = AsyncMock(return_value=None)
        mock_repo.create = AsyncMock(return_value=role)

        with patch("app.services.role_service.AuditService.log", new_callable=AsyncMock) as mock_audit:
            await service.create_role(
                name="Auditor",
                description="Audit role",
                priority=20,
                permissions=["query.submit"],
                actor_identity="admin@example.com",
                db_session=mock_db,
            )

            mock_audit.assert_awaited_once()
            call = mock_audit.call_args
            assert call.kwargs["action"] == AuditActionType.ROLE_CREATE
            assert call.kwargs["actor_identity"] == "admin@example.com"
            assert call.kwargs["resource_type"] == "role"
            assert call.kwargs["resource_id"] == str(role.id)
            assert call.kwargs["outcome"] == "success"
            assert "name" in call.kwargs["context"]
            assert "priority" in call.kwargs["context"]

    async def test_update_role_logs_role_update(self, service, mock_repo, mock_db):
        """Successful role update logs role.update audit event."""
        role = _make_role(name="Analyst", priority=10)
        mock_repo.get_by_id = AsyncMock(return_value=role)
        mock_repo.get_by_name = AsyncMock(return_value=None)
        mock_repo.get_by_priority = AsyncMock(return_value=None)
        mock_repo.update = AsyncMock(return_value=role)

        with patch("app.services.role_service.AuditService.log", new_callable=AsyncMock) as mock_audit:
            await service.update_role(
                role_id=role.id,
                fields={"description": "Updated description"},
                actor_identity="admin@example.com",
                db_session=mock_db,
            )

            mock_audit.assert_awaited_once()
            call = mock_audit.call_args
            assert call.kwargs["action"] == AuditActionType.ROLE_UPDATE
            assert call.kwargs["actor_identity"] == "admin@example.com"
            assert call.kwargs["resource_type"] == "role"
            assert call.kwargs["resource_id"] == str(role.id)
            assert call.kwargs["outcome"] == "success"
            assert "updated_fields" in call.kwargs["context"]

    async def test_delete_role_logs_role_delete(self, service, mock_repo, mock_db):
        """Successful role deletion logs role.delete audit event."""
        role = _make_role(name="Analyst", priority=10)
        mock_repo.get_by_id = AsyncMock(return_value=role)
        mock_repo.delete = AsyncMock(return_value=True)

        with patch("app.services.role_service.AuditService.log", new_callable=AsyncMock) as mock_audit:
            await service.delete_role(
                role_id=role.id,
                actor_identity="admin@example.com",
                db_session=mock_db,
            )

            mock_audit.assert_awaited_once()
            call = mock_audit.call_args
            assert call.kwargs["action"] == AuditActionType.ROLE_DELETE
            assert call.kwargs["actor_identity"] == "admin@example.com"
            assert call.kwargs["resource_type"] == "role"
            assert call.kwargs["resource_id"] == str(role.id)
            assert call.kwargs["outcome"] == "success"

    async def test_builtin_role_update_logs_access_denied(self, service, mock_repo, mock_db):
        """Built-in role update denial logs access.denied audit event."""
        builtin = _make_role(name="Admin", priority=0, is_builtin=True)
        mock_repo.get_by_id = AsyncMock(return_value=builtin)

        with patch("app.services.role_service.AuditService.log", new_callable=AsyncMock) as mock_audit:
            with pytest.raises(BuiltinProtectedError):
                await service.update_role(
                    role_id=builtin.id,
                    fields={"name": "Hacked"},
                    actor_identity="admin@example.com",
                    db_session=mock_db,
                )

            # Should log access.denied BEFORE raising
            mock_audit.assert_awaited_once()
            call = mock_audit.call_args
            assert call.kwargs["action"] == AuditActionType.ACCESS_DENIED
            assert call.kwargs["actor_identity"] == "admin@example.com"
            assert call.kwargs["resource_type"] == "role"
            assert call.kwargs["resource_id"] == str(builtin.id)
            assert call.kwargs["outcome"] == "denied"
            assert call.kwargs["context"]["reason"] == "builtin_protected"

    async def test_builtin_role_delete_logs_access_denied(self, service, mock_repo, mock_db):
        """Built-in role delete denial logs access.denied audit event."""
        builtin = _make_role(name="Admin", priority=0, is_builtin=True)
        mock_repo.get_by_id = AsyncMock(return_value=builtin)
        mock_repo.delete = AsyncMock(
            side_effect=BuiltinProtectedError(resource_type="role", resource_id=str(builtin.id))
        )

        with patch("app.services.role_service.AuditService.log", new_callable=AsyncMock) as mock_audit:
            with pytest.raises(BuiltinProtectedError):
                await service.delete_role(
                    role_id=builtin.id,
                    actor_identity="admin@example.com",
                    db_session=mock_db,
                )

            # Should log access.denied BEFORE raising
            mock_audit.assert_awaited_once()
            call = mock_audit.call_args
            assert call.kwargs["action"] == AuditActionType.ACCESS_DENIED
            assert call.kwargs["actor_identity"] == "admin@example.com"
            assert call.kwargs["resource_type"] == "role"
            assert call.kwargs["resource_id"] == str(builtin.id)
            assert call.kwargs["outcome"] == "denied"
            assert call.kwargs["context"]["reason"] == "builtin_protected"

    async def test_audit_context_no_secrets(self, service, mock_repo, mock_db):
        """Audit context for role create must not contain credentials or secrets."""
        role = _make_role(name="Auditor", priority=20)
        mock_repo.get_by_name = AsyncMock(return_value=None)
        mock_repo.get_by_priority = AsyncMock(return_value=None)
        mock_repo.create = AsyncMock(return_value=role)

        with patch("app.services.role_service.AuditService.log", new_callable=AsyncMock) as mock_audit:
            await service.create_role(
                name="Auditor",
                description="Audit role",
                priority=20,
                permissions=["query.submit"],
                actor_identity="admin@example.com",
                db_session=mock_db,
            )

            call = mock_audit.call_args
            context = call.kwargs["context"]
            context_str = str(context).lower()
            forbidden = ["password", "secret", "token", "credential", "certificate", "privatekey"]
            for term in forbidden:
                assert term not in context_str, f"Audit context leaked '{term}': {context}"


# ── Audit Atomicity ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestAuditAtomicity:
    """If required audit write fails, the protected mutation must not commit."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.delete = MagicMock()
        return db

    @pytest.fixture
    def mock_repo(self, mock_db):
        repo = MagicMock(spec=RoleRepository)
        repo._session = mock_db
        return repo

    @pytest.fixture
    def service(self, mock_repo):
        return RoleService(mock_repo)

    async def test_audit_failure_blocks_role_create(self, service, mock_repo, mock_db):
        """If AuditService.log raises during create_role, exception propagates."""
        role = _make_role(name="Auditor", priority=20)
        mock_repo.get_by_name = AsyncMock(return_value=None)
        mock_repo.get_by_priority = AsyncMock(return_value=None)
        mock_repo.create = AsyncMock(return_value=role)

        with patch(
            "app.services.role_service.AuditService.log",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Audit DB unavailable"),
        ):
            with pytest.raises(RuntimeError, match="Audit DB unavailable"):
                await service.create_role(
                    name="Auditor",
                    description="Audit role",
                    priority=20,
                    permissions=["query.submit"],
                    actor_identity="admin@example.com",
                    db_session=mock_db,
                )

    async def test_audit_failure_blocks_role_update(self, service, mock_repo, mock_db):
        """If AuditService.log raises during update_role, exception propagates."""
        role = _make_role(name="Analyst", priority=10)
        mock_repo.get_by_id = AsyncMock(return_value=role)
        mock_repo.get_by_name = AsyncMock(return_value=None)
        mock_repo.get_by_priority = AsyncMock(return_value=None)
        mock_repo.update = AsyncMock(return_value=role)

        with patch(
            "app.services.role_service.AuditService.log",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Audit DB unavailable"),
        ):
            with pytest.raises(RuntimeError, match="Audit DB unavailable"):
                await service.update_role(
                    role_id=role.id,
                    fields={"description": "Updated"},
                    actor_identity="admin@example.com",
                    db_session=mock_db,
                )

    async def test_audit_failure_blocks_role_delete(self, service, mock_repo, mock_db):
        """If AuditService.log raises during delete_role, exception propagates."""
        role = _make_role(name="Analyst", priority=10)
        mock_repo.get_by_id = AsyncMock(return_value=role)
        mock_repo.delete = AsyncMock(return_value=True)

        with patch(
            "app.services.role_service.AuditService.log",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Audit DB unavailable"),
        ):
            with pytest.raises(RuntimeError, match="Audit DB unavailable"):
                await service.delete_role(
                    role_id=role.id,
                    actor_identity="admin@example.com",
                    db_session=mock_db,
                )


# ── Group Mapping Endpoint Audit Logging ────────────────────────────────────


@pytest.mark.asyncio
class TestGroupMappingAuditLogging:
    """AuditService.log is called during group mapping create/delete."""

    def _build_app(self, session=None):
        """Build isolated FastAPI app with router, exception handler, and optional session."""
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import JSONResponse
        from starlette.middleware.base import BaseHTTPMiddleware

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

            class InjectSessionMiddleware(BaseHTTPMiddleware):
                async def dispatch(self, request, call_next):
                    _sess = dict(session)
                    if "role_id" not in _sess:
                        _sess["role_id"] = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
                    request.state.session = _sess
                    return await call_next(request)

            app.add_middleware(InjectSessionMiddleware)

        return app

    async def test_create_group_mapping_logs_role_mapping_change(self):
        """POST /admin/sso/group-mappings logs role.mapping.change."""
        app = self._build_app(session={"permissions": ["admin.roles.manage"], "username": "admin@example.com"})

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

        with patch("app.api.v1.admin_sso.AuditService.log", new_callable=AsyncMock) as mock_audit:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/admin/sso/group-mappings",
                    json={"sso_group_value": "analysts", "role_id": str(role.id)},
                    headers={"origin": "http://test"},
                )

            assert response.status_code == 201
            mock_audit.assert_awaited_once()
            call = mock_audit.call_args
            assert call.kwargs["action"] == AuditActionType.ROLE_MAPPING_CHANGE
            assert call.kwargs["actor_identity"] == "admin@example.com"
            assert call.kwargs["resource_type"] == "sso_group_mapping"
            assert call.kwargs["outcome"] == "success"
            assert call.kwargs["context"]["action"] == "create"
            assert call.kwargs["context"]["sso_group_value"] == "analysts"

    async def test_delete_group_mapping_logs_role_mapping_change(self):
        """DELETE /admin/sso/group-mappings/{id} logs role.mapping.change."""
        app = self._build_app(session={"permissions": ["admin.roles.manage"], "username": "admin@example.com"})

        from app.core.dependencies import get_db

        mapping = _make_mapping()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([mapping]))
        mock_db.commit = AsyncMock()

        app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.api.v1.admin_sso.AuditService.log", new_callable=AsyncMock) as mock_audit:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.delete(
                    f"/api/v1/admin/sso/group-mappings/{mapping.id}",
                    headers={"origin": "http://test"},
                )

            assert response.status_code == 204
            mock_audit.assert_awaited_once()
            call = mock_audit.call_args
            assert call.kwargs["action"] == AuditActionType.ROLE_MAPPING_CHANGE
            assert call.kwargs["actor_identity"] == "admin@example.com"
            assert call.kwargs["resource_type"] == "sso_group_mapping"
            assert call.kwargs["outcome"] == "success"
            assert call.kwargs["context"]["action"] == "delete"

    async def test_group_mapping_audit_context_no_secrets(self):
        """Audit context for group mapping must not contain credentials or role internals."""
        app = self._build_app(session={"permissions": ["admin.roles.manage"], "username": "admin@example.com"})

        from app.core.dependencies import get_db

        role = _make_role(name="Analyst")
        mapping = _make_mapping(role_id=role.id)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),
                FakeResult([role]),
                FakeResult([mapping]),
            ]
        )
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.add = MagicMock()

        app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.api.v1.admin_sso.AuditService.log", new_callable=AsyncMock) as mock_audit:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/admin/sso/group-mappings",
                    json={"sso_group_value": "analysts", "role_id": str(role.id)},
                    headers={"origin": "http://test"},
                )

            assert response.status_code == 201
            call = mock_audit.call_args
            context = call.kwargs["context"]
            context_str = str(context).lower()
            forbidden = ["password", "secret", "token", "credential", "certificate"]
            for term in forbidden:
                assert term not in context_str, f"Audit context leaked '{term}': {context}"

    async def test_audit_failure_blocks_group_mapping_create(self):
        """If AuditService.log raises during create_group_mapping, exception propagates."""
        app = self._build_app(session={"permissions": ["admin.roles.manage"], "username": "admin@example.com"})

        from app.core.dependencies import get_db

        role = _make_role(name="Analyst")
        mapping = _make_mapping(role_id=role.id)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),
                FakeResult([role]),
                FakeResult([mapping]),
            ]
        )
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.add = MagicMock()

        app.dependency_overrides[get_db] = lambda: mock_db

        with patch(
            "app.api.v1.admin_sso.AuditService.log",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Audit DB unavailable"),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/admin/sso/group-mappings",
                    json={"sso_group_value": "analysts", "role_id": str(role.id)},
                    headers={"origin": "http://test"},
                )

            # Audit failure should cause 500 before commit
            assert response.status_code == 500
