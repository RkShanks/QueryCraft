"""AuthService — login, logout, session management."""

import json
import os
import time
import uuid

from fastapi import HTTPException, status
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.security import verify_password
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserProfile


class AuthService:
    """Handles authentication and session lifecycle."""

    def __init__(
        self,
        user_repository: UserRepository,
        redis: Redis,
        settings: Settings | None = None,
    ):
        self._repo = user_repository
        self._redis = redis
        self._settings = settings or get_settings()

    async def sign_in(self, username: str, password: str) -> tuple[UserProfile, str]:
        """Authenticate user and create a Redis-backed session.

        Phase 5 (FR-120): Local password login is admin-only.
        - SSO users (auth_provider != 'local') are rejected with generic 401.
        - Non-admin local users are rejected with generic 401.
        - Generic error prevents account existence or auth-provider leak.
        """
        user = await self._repo.get_by_username(username)

        _unauthorized = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )

        if user is None:
            raise _unauthorized

        # Phase 5: only local admin users may use local password login
        auth_provider = getattr(user, "auth_provider", "local")
        auth_provider = auth_provider if isinstance(auth_provider, str) else "local"

        if auth_provider != "local":
            raise _unauthorized

        if user.password_hash is None or not verify_password(password, user.password_hash):
            raise _unauthorized

        # Non-admin local users are also rejected (admin-only local login)
        user_role = getattr(user, "role", "")
        if not isinstance(user_role, str):
            user_role = ""
        if user_role != "admin":
            raise _unauthorized

        session_id = os.urandom(32).hex()

        def _real_str_attr(obj, attr, default):
            val = getattr(obj, attr, default)
            return val if isinstance(val, str) else default

        # Resolve role-derived fields from user.role_obj if available
        _role_id = getattr(user, "role_id", None)
        role_id = str(_role_id) if isinstance(_role_id, (uuid.UUID, str)) else None
        role_name = None
        permissions: list[str] = []
        role_obj = getattr(user, "role_obj", None)
        if role_obj is not None:
            _name = getattr(role_obj, "name", None)
            if isinstance(_name, str):
                role_name = _name
            _perms = getattr(role_obj, "permissions", None)
            if isinstance(_perms, (list, tuple, set)):
                permissions = list(_perms)

        auth_provider = _real_str_attr(user, "auth_provider", "local")
        # Local users: subject_id defaults to username
        subject_id = username if auth_provider == "local" else _real_str_attr(user, "subject_id", username)

        session_data = {
            "user_id": str(user.id),
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "role_id": role_id,
            "role_name": role_name,
            "permissions": permissions,
            "auth_provider": auth_provider,
            "subject_id": subject_id,
            "created_at": time.time(),
            "last_activity": time.time(),
        }
        ttl_seconds = self._settings.SESSION_IDLE_TIMEOUT_HOURS * 3600
        await self._redis.set(
            f"session:{session_id}",
            json.dumps(session_data),
            ex=ttl_seconds,
        )

        profile = UserProfile(
            id=str(user.id),
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            role_id=role_id,
            role_name=role_name,
            permissions=permissions,
            auth_provider=auth_provider,
        )
        return profile, session_id

    async def sign_out(self, session_id: str) -> None:
        """Delete the session from Redis."""
        await self._redis.delete(f"session:{session_id}")

    async def get_me(self, session_id: str) -> UserProfile:
        """Return the user profile for the given session.

        Validates the user still exists in the database. If the user has been
        deleted, the stale Redis session is cleaned up and a 401 is raised.
        """
        raw = await self._redis.get(f"session:{session_id}")
        if raw is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthorized", "message_key": "error.unauthorized"},
            )
        data = json.loads(raw)
        user_id = uuid.UUID(data["user_id"])
        user = await self._repo.get_by_id(user_id)
        if user is None:
            await self._redis.delete(f"session:{session_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthorized", "message_key": "error.unauthorized"},
            )
        # Prefer session data for Phase 5 fields (source of truth for active session)
        return UserProfile(
            id=str(user.id),
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            role_id=data.get("role_id"),
            role_name=data.get("role_name"),
            permissions=data.get("permissions", []),
            auth_provider=data.get("auth_provider", "local"),
        )
