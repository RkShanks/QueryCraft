"""AuthService — login, logout, session management."""

import hashlib
import json
import os
import time
import uuid
from typing import Never

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import verify_password
from app.db.models.enums import AuditActionType
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserProfile
from app.services.audit_service import AuditService


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

    async def sign_in(
        self,
        username: str,
        password: str,
        db_session: AsyncSession | None = None,
    ) -> tuple[UserProfile, str]:
        """Authenticate user and create a Redis-backed session.

        Phase 5 (FR-120): Local password login is admin-only.
        - SSO users (auth_provider != 'local') are rejected with generic 401.
        - Non-admin local users are rejected with generic 401.
        - Generic error prevents account existence or auth-provider leak.
        - When a database session is provided, every attempt is durably audited.
        """
        user = await self._repo.get_by_username(username)

        _unauthorized = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )

        async def reject_login() -> Never:
            if db_session is not None:
                await AuditService.log(
                    db_session,
                    action=AuditActionType.AUTH_LOGIN_FAILURE,
                    resource_type="session",
                    outcome="failure",
                    context={
                        "auth_provider": "local",
                        "error_code": "unauthorized",
                    },
                )
                await db_session.commit()
            raise _unauthorized

        if user is None:
            await reject_login()

        # Phase 5: only local admin users may use local password login
        auth_provider = getattr(user, "auth_provider", "local")
        auth_provider = auth_provider if isinstance(auth_provider, str) else "local"

        if auth_provider != "local":
            await reject_login()

        if user.password_hash is None or not verify_password(password, user.password_hash):
            await reject_login()

        # Non-admin local users are also rejected (admin-only local login)
        user_role = getattr(user, "role", "")
        if not isinstance(user_role, str):
            user_role = ""
        if user_role != "admin":
            await reject_login()

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

        # Enforce concurrent session limit per user (FR-127, S-010)
        await self._enforce_concurrent_session_limit(str(user.id), session_id, session_data["created_at"])

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

        if db_session is not None:
            try:
                await AuditService.log(
                    db_session,
                    action=AuditActionType.AUTH_LOGIN_SUCCESS,
                    actor_id=user.id,
                    actor_identity=user.username,
                    resource_type="user",
                    resource_id=str(user.id),
                    outcome="success",
                    context={
                        "auth_provider": "local",
                        "role_name": role_name,
                    },
                )
                await db_session.commit()
            except Exception:
                await self.sign_out(session_id)
                raise

        return profile, session_id

    async def _enforce_concurrent_session_limit(
        self,
        user_id: str,
        new_session_id: str,
        created_at: float,
    ) -> None:
        """Delegate to shared SessionRepository eviction logic."""
        max_sessions = getattr(self._settings, "MAX_CONCURRENT_SESSIONS_PER_USER", 5)
        ttl_seconds = self._settings.SESSION_IDLE_TIMEOUT_HOURS * 3600
        await SessionRepository.enforce_concurrent_session_limit(
            self._redis,
            user_id,
            new_session_id,
            created_at,
            max_sessions,
            ttl_seconds,
        )

    async def sign_out(
        self,
        session_id: str,
        db_session: AsyncSession | None = None,
    ) -> None:
        """Delete the session from Redis and clean up user index.

        Emits an ``auth.logout`` audit entry when a DB session is
        provided. The actor is the username pulled from the session
        blob. The resource_id is **never** the raw session token:
        it is a SHA-256 digest with prefix ``sha256:`` so the audit
        log retains a stable, non-reversible identifier for
        correlation. Audit failures propagate (fail-closed) per
        the project-wide contract used by role_service,
        sso_service, and query_service.
        """
        # Remove from user session index first (need to discover user_id)
        raw = await self._redis.get(f"session:{session_id}")
        actor_identity: str | None = None
        if raw:
            try:
                data = json.loads(raw)
                user_id = data.get("user_id")
                if user_id:
                    await self._redis.zrem(f"user_sessions:{user_id}", session_id)
                _uname = data.get("username")
                if isinstance(_uname, str):
                    actor_identity = _uname
            except Exception:
                pass  # sanitize — never leak raw session content
        await self._redis.delete(f"session:{session_id}")

        if db_session is not None:
            session_token_digest = "sha256:" + hashlib.sha256(session_id.encode("utf-8")).hexdigest()
            await AuditService.log(
                db_session,
                action=AuditActionType.AUTH_LOGOUT,
                actor_identity=actor_identity,
                resource_type="session",
                resource_id=session_token_digest,
                outcome="success",
                context={},
            )

    async def get_me(self, session_id: str) -> UserProfile:
        """Return the user profile for the given session.

        Validates the user and resolves role permissions from the database on
        every request. Redis stores the refreshed values for consumers, but
        never remains the authorization source after a role changes.
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
        role_obj = getattr(user, "role_obj", None)
        permissions: list[str] = []
        role_id: str | None = None
        role_name: str | None = None
        if role_obj is not None:
            _perms = getattr(role_obj, "permissions", None)
            if isinstance(_perms, (list, tuple, set)):
                permissions = list(_perms)
            _role_id = getattr(role_obj, "id", None)
            _role_name = getattr(role_obj, "name", None)
            role_id = str(_role_id) if _role_id is not None else None
            role_name = _role_name if isinstance(_role_name, str) else None

        if (
            data.get("permissions") != permissions
            or data.get("role_id") != role_id
            or data.get("role_name") != role_name
        ):
            data["permissions"] = permissions
            data["role_id"] = role_id
            data["role_name"] = role_name
            ttl_seconds = self._settings.SESSION_IDLE_TIMEOUT_HOURS * 3600
            await self._redis.set(
                f"session:{session_id}",
                json.dumps(data),
                ex=ttl_seconds,
            )

        return UserProfile(
            id=str(user.id),
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            role_id=role_id,
            role_name=role_name,
            permissions=permissions,
            auth_provider=data.get("auth_provider", "local"),
        )
