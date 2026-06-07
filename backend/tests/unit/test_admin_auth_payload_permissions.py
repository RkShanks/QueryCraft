"""TDD tests for SMOKE-001 — Built-in admin session must include full Admin role permissions.

Post-freeze full browser smoke found that the built-in admin session stored
in Redis lacks ``admin.audit.verify`` (and the other Admin role permissions)
in the ``/api/v1/auth/me`` payload. The ``PermissionGuard`` on ``/admin/audit``
then redirects the admin to ``/``.

These tests pin down the contract:
* ``AuthService.sign_in`` must populate the Redis session with all permissions
  from the user's ``role_obj`` (the built-in Admin role has six).
* ``AuthService.get_me`` must refresh a stale Redis session whose ``permissions``
  list is empty (e.g. created before the fix landed) by re-reading the role
  from the database and updating the session in-place.
* ``UserRepository.get_by_username`` / ``get_by_id`` must eagerly load
  ``User.role_obj`` so the relationship is available without a second round-trip
  (defence in depth — the model already declares ``lazy="selectin"``, but an
  explicit ``selectinload`` makes the intent unambiguous).
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

from app.db.models.role import Role
from app.db.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService

BUILTIN_ADMIN_PERMISSIONS = {
    "query.submit",
    "query.history.view",
    "admin.connections.manage",
    "admin.roles.manage",
    "admin.sso.manage",
    "admin.audit.verify",
}


async def _ensure_admin_has_role(db_session) -> uuid.UUID:
    """Make sure the seeded admin user points at the built-in Admin role.

    Returns the Admin role's UUID. Tests that need a fully-wired admin user
    (role_id → Admin role with all six permissions) call this first.
    """
    role_row = (
        await db_session.execute(text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true"))
    ).first()
    assert role_row is not None, "Built-in Admin role must be seeded by migration 007"
    role_id = role_row[0]

    await db_session.execute(
        text(
            "UPDATE users SET role_id = CAST(:rid AS uuid), is_builtin = true, "
            "auth_provider = 'local' WHERE username = 'admin'"
        ),
        {"rid": str(role_id)},
    )
    await db_session.commit()
    return role_id


async def _get_admin_id(db_session) -> uuid.UUID:
    row = (await db_session.execute(text("SELECT id FROM users WHERE username = 'admin'"))).first()
    assert row is not None, "Built-in admin user must be seeded"
    return row[0]


class TestSignInBuiltinAdminPermissions:
    """sign_in must populate the Redis session with the full Admin permission set."""

    @pytest.mark.asyncio
    async def test_sign_in_returns_all_six_admin_permissions(self, db_session, redis_client):
        """Built-in admin login returns the six Admin role permissions on the profile."""
        await _ensure_admin_has_role(db_session)
        repo = UserRepository(db_session)
        service = AuthService(repo, redis_client)

        profile, session_id = await service.sign_in("admin", "admin123")

        assert profile.username == "admin"
        for perm in BUILTIN_ADMIN_PERMISSIONS:
            assert perm in profile.permissions, f"Missing permission: {perm}"

        raw = await redis_client.get(f"session:{session_id}")
        assert raw is not None
        session = json.loads(raw)
        for perm in BUILTIN_ADMIN_PERMISSIONS:
            assert perm in session["permissions"], f"Missing permission in session: {perm}"


class TestGetMeRefreshesStaleSession:
    """get_me must refresh a session whose permissions list is empty."""

    @pytest.mark.asyncio
    async def test_get_me_refreshes_empty_permissions_from_role(self, db_session, redis_client):
        """A stale session (permissions=[]) is refreshed from the user's role_obj."""
        role_id = await _ensure_admin_has_role(db_session)
        repo = UserRepository(db_session)
        service = AuthService(repo, redis_client)

        # Fetch the admin user's id for the stale session payload
        admin_id = await _get_admin_id(db_session)

        # Pre-populate Redis with a stale session that lacks permissions
        session_id = "stale-session-001"
        stale_payload = {
            "user_id": str(admin_id),
            "username": "admin",
            "display_name": "Platform Administrator",
            "role": "admin",
            "role_id": str(role_id),
            "role_name": "Admin",
            "permissions": [],  # STALE — pre-fix sessions stored empty
            "auth_provider": "local",
            "subject_id": "admin",
            "created_at": 1.0,
            "last_activity": 1.0,
        }
        await redis_client.set(
            f"session:{session_id}",
            json.dumps(stale_payload),
            ex=3600,
        )

        profile = await service.get_me(session_id)

        # The response must include all six Admin permissions
        for perm in BUILTIN_ADMIN_PERMISSIONS:
            assert perm in profile.permissions, f"get_me did not refresh stale session: missing {perm}"

        # The Redis session must be updated in-place so subsequent calls don't re-refresh
        refreshed = json.loads(await redis_client.get(f"session:{session_id}"))
        for perm in BUILTIN_ADMIN_PERMISSIONS:
            assert perm in refreshed["permissions"]

    @pytest.mark.asyncio
    async def test_get_me_returns_session_permissions_when_not_stale(self, db_session, redis_client):
        """A session that already has permissions is returned as-is (no unnecessary refresh)."""
        await _ensure_admin_has_role(db_session)
        repo = UserRepository(db_session)
        service = AuthService(repo, redis_client)

        admin_id = await _get_admin_id(db_session)

        session_id = "fresh-session-001"
        fresh_payload = {
            "user_id": str(admin_id),
            "username": "admin",
            "display_name": "Platform Administrator",
            "role": "admin",
            "role_id": str(uuid.uuid4()),
            "role_name": "CustomRole",
            "permissions": ["query.submit", "query.history.view"],
            "auth_provider": "local",
            "subject_id": "admin",
            "created_at": 1.0,
            "last_activity": 1.0,
        }
        await redis_client.set(f"session:{session_id}", json.dumps(fresh_payload), ex=3600)

        profile = await service.get_me(session_id)

        # Session data is the source of truth when not stale
        assert profile.role_name == "CustomRole"
        assert "query.submit" in profile.permissions
        assert "admin.audit.verify" not in profile.permissions


class TestUserRepositoryEagerLoadsRoleObj:
    """UserRepository.get_by_username / get_by_id must eagerly load role_obj."""

    @pytest.mark.asyncio
    async def test_get_by_username_loads_role_obj(self, db_session):
        """get_by_username returns a User with role_obj populated (no lazy-load after session close)."""
        await _ensure_admin_has_role(db_session)
        repo = UserRepository(db_session)

        user = await repo.get_by_username("admin")

        assert user is not None
        assert user.username == "admin"
        # role_obj must be loaded eagerly — accessing it must NOT raise
        # MissingGreenlet or DetachedInstanceError after the request ends.
        assert user.role_obj is not None, "role_obj must be eagerly loaded"
        assert user.role_obj.name == "Admin"
        for perm in BUILTIN_ADMIN_PERMISSIONS:
            assert perm in user.role_obj.permissions

    @pytest.mark.asyncio
    async def test_get_by_id_loads_role_obj(self, db_session):
        """get_by_id returns a User with role_obj populated."""
        await _ensure_admin_has_role(db_session)
        admin_id = await _get_admin_id(db_session)
        repo = UserRepository(db_session)

        user = await repo.get_by_id(admin_id)

        assert user is not None
        assert user.role_obj is not None
        assert user.role_obj.name == "Admin"
        for perm in BUILTIN_ADMIN_PERMISSIONS:
            assert perm in user.role_obj.permissions


class TestGetMeStaleSessionRefreshUnit:
    """Unit-level test for get_me's stale-session refresh path (no real DB needed)."""

    @pytest.mark.asyncio
    async def test_get_me_calls_get_by_id_for_refresh(self):
        """get_me must call get_by_id (which loads role_obj) to refresh stale sessions."""
        mock_repo = AsyncMock()

        admin_id = uuid.uuid4()
        role_id = uuid.uuid4()
        role = MagicMock(spec=Role)
        role.id = role_id
        role.name = "Admin"
        role.permissions = list(BUILTIN_ADMIN_PERMISSIONS)

        user = MagicMock(spec=User)
        user.id = admin_id
        user.username = "admin"
        user.display_name = "Platform Administrator"
        user.role = "admin"
        user.role_id = role_id
        user.auth_provider = "local"
        user.role_obj = role

        mock_repo.get_by_id.return_value = user

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(
            {
                "user_id": str(admin_id),
                "username": "admin",
                "display_name": "Platform Administrator",
                "role": "admin",
                "role_id": str(role_id),
                "role_name": "Admin",
                "permissions": [],
                "auth_provider": "local",
                "subject_id": "admin",
            }
        )
        mock_redis.set = AsyncMock()

        service = AuthService(mock_repo, mock_redis)
        profile = await service.get_me("sess-1")

        # get_by_id must be called so role_obj can be loaded
        mock_repo.get_by_id.assert_awaited_once_with(admin_id)
        # Stale session must be updated in Redis with fresh permissions
        assert mock_redis.set.await_count >= 1
        for perm in BUILTIN_ADMIN_PERMISSIONS:
            assert perm in profile.permissions
