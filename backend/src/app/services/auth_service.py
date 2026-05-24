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
        """Authenticate user and create a Redis-backed session."""
        user = await self._repo.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthorized", "message_key": "error.unauthorized"},
            )

        session_id = os.urandom(32).hex()

        # Resolve role-derived fields from user.role_obj if available
        role_id = str(user.role_id) if user.role_id else None
        role_name = None
        permissions: list[str] = []
        if getattr(user, "role_obj", None) is not None:
            role_name = user.role_obj.name
            permissions = list(user.role_obj.permissions) if user.role_obj.permissions else []

        auth_provider = getattr(user, "auth_provider", "local")
        # Local users: subject_id defaults to username
        subject_id = username if auth_provider == "local" else getattr(user, "subject_id", username)

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
