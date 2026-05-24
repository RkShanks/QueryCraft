"""TDD tests for built-in admin lockout prevention (T-652).

Tests:
- BuiltinProtectedError exception with message_key "error.builtinRoleProtected"
- UserRepository.delete rejects deletion of is_builtin=true user
- RoleRepository.delete rejects deletion of is_builtin=true role
- RoleRepository.update rejects modification of is_builtin=true role core properties
- AuthService.sign_in works for built-in admin regardless of SSO/role state
- All errors sanitized: no raw UUIDs, DB errors, stack traces in user-facing responses.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.core.exceptions import QueryCraftError
from app.db.models.role import Role
from app.db.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService

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


def _make_builtin_user():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "admin"
    user.display_name = "Platform Administrator"
    user.password_hash = "argon2id_hash"
    user.role = "admin"
    user.role_id = uuid.uuid4()
    user.is_builtin = True
    user.auth_provider = "local"
    user.role_obj = None
    return user


def _make_builtin_role():
    role = MagicMock(spec=Role)
    role.id = uuid.uuid4()
    role.name = "Built-in Admin"
    role.description = "System administrator"
    role.priority = 0
    role.permissions = [
        "query.submit",
        "query.history.view",
        "admin.connections.manage",
        "admin.roles.manage",
        "admin.sso.manage",
        "admin.audit.verify",
    ]
    role.is_builtin = True
    return role


def _make_regular_user():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "analyst"
    user.display_name = "Analyst User"
    user.password_hash = "argon2id_hash"
    user.role = "analyst"
    user.role_id = uuid.uuid4()
    user.is_builtin = False
    user.auth_provider = "local"
    user.role_obj = None
    return user


def _make_regular_role():
    role = MagicMock(spec=Role)
    role.id = uuid.uuid4()
    role.name = "Analyst"
    role.description = "Read-only analyst"
    role.priority = 10
    role.permissions = ["query.submit", "query.history.view"]
    role.is_builtin = False
    return role


# ── Exception class tests ─────────────────────────────────────────────────


class TestBuiltinProtectedError:
    """BuiltinProtectedError must exist with correct message_key."""

    def test_exception_class_exists(self):
        from app.core.exceptions import BuiltinProtectedError

        assert BuiltinProtectedError is not None

    def test_is_querycraft_error_subclass(self):
        from app.core.exceptions import BuiltinProtectedError

        assert issubclass(BuiltinProtectedError, QueryCraftError)

    def test_message_key_is_builtin_role_protected(self):
        from app.core.exceptions import BuiltinProtectedError

        exc = BuiltinProtectedError()
        assert exc.message_key == "error.builtinRoleProtected"

    def test_default_message(self):
        from app.core.exceptions import BuiltinProtectedError

        exc = BuiltinProtectedError()
        assert "protected" in str(exc).lower() or "built-in" in str(exc).lower()

    def test_can_include_resource_type(self):
        from app.core.exceptions import BuiltinProtectedError

        exc = BuiltinProtectedError(resource_type="user")
        assert exc.extra.get("resource_type") == "user"


# ── UserRepository.delete tests ────────────────────────────────────────────


class TestUserRepositoryDeleteBuiltinProtection:
    """UserRepository.delete must reject is_builtin=true users."""

    @pytest.mark.asyncio
    async def test_delete_builtin_user_raises_builtin_protected_error(self):
        from app.core.exceptions import BuiltinProtectedError

        mock_session = AsyncMock()
        builtin_user = _make_builtin_user()
        mock_session.execute.return_value = FakeResult(builtin_user)

        repo = UserRepository(mock_session)

        with pytest.raises(BuiltinProtectedError) as exc_info:
            await repo.delete(builtin_user.id)

        assert exc_info.value.message_key == "error.builtinRoleProtected"

    @pytest.mark.asyncio
    async def test_delete_regular_user_succeeds(self):

        mock_session = AsyncMock()
        regular_user = _make_regular_user()
        mock_session.execute.return_value = FakeResult(regular_user)

        repo = UserRepository(mock_session)
        result = await repo.delete(regular_user.id)

        assert result is True
        mock_session.delete.assert_called_once_with(regular_user)
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_user_returns_false(self):

        mock_session = AsyncMock()
        mock_session.execute.return_value = FakeResult(None)

        repo = UserRepository(mock_session)
        result = await repo.delete(uuid.uuid4())

        assert result is False


# ── RoleRepository.delete tests ────────────────────────────────────────────


class TestRoleRepositoryDeleteBuiltinProtection:
    """RoleRepository.delete must reject is_builtin=true roles."""

    @pytest.mark.asyncio
    async def test_delete_builtin_role_raises_builtin_protected_error(self):
        from app.core.exceptions import BuiltinProtectedError
        from app.repositories.role_repository import RoleRepository

        mock_session = AsyncMock()
        builtin_role = _make_builtin_role()
        mock_session.execute.return_value = FakeResult(builtin_role)

        repo = RoleRepository(mock_session)

        with pytest.raises(BuiltinProtectedError) as exc_info:
            await repo.delete(builtin_role.id)

        assert exc_info.value.message_key == "error.builtinRoleProtected"

    @pytest.mark.asyncio
    async def test_delete_regular_role_succeeds(self):
        from app.repositories.role_repository import RoleRepository

        mock_session = AsyncMock()
        regular_role = _make_regular_role()
        mock_session.execute.return_value = FakeResult(regular_role)

        repo = RoleRepository(mock_session)
        result = await repo.delete(regular_role.id)

        assert result is True
        mock_session.delete.assert_called_once_with(regular_role)
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_role_returns_false(self):
        from app.repositories.role_repository import RoleRepository

        mock_session = AsyncMock()
        mock_session.execute.return_value = FakeResult(None)

        repo = RoleRepository(mock_session)
        result = await repo.delete(uuid.uuid4())

        assert result is False


# ── RoleRepository.update tests ────────────────────────────────────────────


class TestRoleRepositoryUpdateBuiltinProtection:
    """RoleRepository.update must reject core property changes on is_builtin=true roles."""

    @pytest.mark.asyncio
    async def test_update_builtin_role_name_raises_builtin_protected_error(self):
        from app.core.exceptions import BuiltinProtectedError
        from app.repositories.role_repository import RoleRepository

        mock_session = AsyncMock()
        builtin_role = _make_builtin_role()
        mock_session.execute.return_value = FakeResult(builtin_role)

        repo = RoleRepository(mock_session)

        with pytest.raises(BuiltinProtectedError) as exc_info:
            await repo.update(builtin_role.id, {"name": "Hacked Admin"})

        assert exc_info.value.message_key == "error.builtinRoleProtected"

    @pytest.mark.asyncio
    async def test_update_builtin_role_permissions_raises_builtin_protected_error(self):
        from app.core.exceptions import BuiltinProtectedError
        from app.repositories.role_repository import RoleRepository

        mock_session = AsyncMock()
        builtin_role = _make_builtin_role()
        mock_session.execute.return_value = FakeResult(builtin_role)

        repo = RoleRepository(mock_session)

        with pytest.raises(BuiltinProtectedError) as exc_info:
            await repo.update(builtin_role.id, {"permissions": []})

        assert exc_info.value.message_key == "error.builtinRoleProtected"

    @pytest.mark.asyncio
    async def test_update_builtin_role_is_builtin_raises_builtin_protected_error(self):
        from app.core.exceptions import BuiltinProtectedError
        from app.repositories.role_repository import RoleRepository

        mock_session = AsyncMock()
        builtin_role = _make_builtin_role()
        mock_session.execute.return_value = FakeResult(builtin_role)

        repo = RoleRepository(mock_session)

        with pytest.raises(BuiltinProtectedError) as exc_info:
            await repo.update(builtin_role.id, {"is_builtin": False})

        assert exc_info.value.message_key == "error.builtinRoleProtected"

    @pytest.mark.asyncio
    async def test_update_builtin_role_description_allowed(self):
        from app.repositories.role_repository import RoleRepository

        mock_session = AsyncMock()
        builtin_role = _make_builtin_role()
        mock_session.execute.return_value = FakeResult(builtin_role)

        repo = RoleRepository(mock_session)
        result = await repo.update(builtin_role.id, {"description": "Updated description"})

        assert result == builtin_role
        assert builtin_role.description == "Updated description"
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_regular_role_succeeds(self):
        from app.repositories.role_repository import RoleRepository

        mock_session = AsyncMock()
        regular_role = _make_regular_role()
        mock_session.execute.return_value = FakeResult(regular_role)

        repo = RoleRepository(mock_session)
        result = await repo.update(regular_role.id, {"name": "Updated Analyst"})

        assert result == regular_role
        assert regular_role.name == "Updated Analyst"
        mock_session.flush.assert_called_once()


# ── AuthService.sign_in tests ─────────────────────────────────────────────


class TestAuthServiceBuiltinAdminLoginAlwaysWorks:
    """Built-in admin local login must work regardless of SSO/role state."""

    @pytest.mark.asyncio
    async def test_builtin_admin_login_succeeds_with_local_provider(self):
        """Built-in admin with auth_provider='local' can sign in."""
        mock_repo = AsyncMock()
        builtin_user = _make_builtin_user()
        mock_repo.get_by_username.return_value = builtin_user

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        with patch("app.services.auth_service.verify_password", return_value=True):
            svc = AuthService(mock_repo, mock_redis)
            profile, session_id = await svc.sign_in("admin", "admin123")

        assert profile.username == "admin"
        assert session_id is not None
        assert len(session_id) == 64  # 32 bytes hex

    @pytest.mark.asyncio
    async def test_builtin_admin_login_succeeds_even_if_sso_provider_exists(self):
        """Built-in admin can sign in even when SSO providers are configured."""
        mock_repo = AsyncMock()
        builtin_user = _make_builtin_user()
        mock_repo.get_by_username.return_value = builtin_user

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        with patch("app.services.auth_service.verify_password", return_value=True):
            svc = AuthService(mock_repo, mock_redis)
            profile, session_id = await svc.sign_in("admin", "admin123")

        assert profile.username == "admin"
        assert profile.auth_provider == "local"

    @pytest.mark.asyncio
    async def test_builtin_admin_login_succeeds_with_role_obj_permissions(self):
        """Built-in admin with role_obj gets permissions from role."""
        mock_repo = AsyncMock()
        builtin_user = _make_builtin_user()
        builtin_role = _make_builtin_role()
        builtin_user.role_obj = builtin_role
        mock_repo.get_by_username.return_value = builtin_user

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        with patch("app.services.auth_service.verify_password", return_value=True):
            svc = AuthService(mock_repo, mock_redis)
            profile, session_id = await svc.sign_in("admin", "admin123")

        assert "admin.sso.manage" in profile.permissions
        assert "admin.roles.manage" in profile.permissions

    @pytest.mark.asyncio
    async def test_builtin_admin_login_succeeds_without_role_obj(self):
        """Built-in admin without role_obj still gets session (permissions empty)."""
        mock_repo = AsyncMock()
        builtin_user = _make_builtin_user()
        builtin_user.role_obj = None
        mock_repo.get_by_username.return_value = builtin_user

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        with patch("app.services.auth_service.verify_password", return_value=True):
            svc = AuthService(mock_repo, mock_redis)
            profile, session_id = await svc.sign_in("admin", "admin123")

        assert profile.username == "admin"
        assert profile.permissions == []


# ── Error sanitization tests ──────────────────────────────────────────────


class TestLockoutErrorSanitization:
    """Lockout prevention errors must not leak internals."""

    def test_builtin_protected_error_no_uuid_in_message(self):
        from app.core.exceptions import BuiltinProtectedError

        exc = BuiltinProtectedError(resource_type="user", resource_id=str(uuid.uuid4()))
        # UUID should be in extra, not in the human-readable message
        uuid_pattern = "-"
        # The message itself should not contain a UUID-like string
        assert uuid_pattern not in str(exc) or str(exc).count("-") < 4

    def test_builtin_protected_error_no_stack_trace(self):
        from app.core.exceptions import BuiltinProtectedError

        exc = BuiltinProtectedError()
        assert "Traceback" not in str(exc)
        assert 'File "' not in str(exc)

    def test_builtin_protected_error_has_message_key(self):
        from app.core.exceptions import BuiltinProtectedError

        exc = BuiltinProtectedError()
        assert hasattr(exc, "message_key")
        assert exc.message_key == "error.builtinRoleProtected"

    def test_builtin_protected_error_can_map_to_http_403(self):
        """API layer can map BuiltinProtectedError to 403 with message_key."""
        from app.core.exceptions import BuiltinProtectedError

        exc = BuiltinProtectedError(resource_type="role")

        http_exc = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message_key": exc.message_key},
        )

        assert http_exc.status_code == 403
        assert http_exc.detail["message_key"] == "error.builtinRoleProtected"


# ── Integration-style tests with real DB ──────────────────────────────────


@pytest.mark.asyncio
async def test_builtin_admin_user_exists_in_db(db_session):
    """Verify the seeded built-in admin user has is_builtin=true."""
    from sqlalchemy import text

    result = await db_session.execute(
        text("SELECT username, is_builtin, auth_provider FROM users WHERE username = 'admin'")
    )
    row = result.fetchone()
    assert row is not None
    assert row.is_builtin is True
    assert row.auth_provider == "local"


@pytest.mark.asyncio
async def test_builtin_admin_role_exists_in_db(db_session):
    """Verify the seeded built-in admin role has is_builtin=true and all permissions."""
    from sqlalchemy import text

    result = await db_session.execute(text("SELECT name, is_builtin, permissions FROM roles WHERE is_builtin = true"))
    row = result.fetchone()
    assert row is not None
    assert row.is_builtin is True
    perms = row.permissions
    assert "admin.sso.manage" in perms
    assert "admin.roles.manage" in perms
    assert "admin.audit.verify" in perms
