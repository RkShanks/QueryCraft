"""AuthService — login, logout, session management."""

import json
import os
import time

from fastapi import HTTPException, status
from redis.asyncio import Redis

from app.core.security import verify_password
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserProfile


class AuthService:
    """Handles authentication and session lifecycle."""

    def __init__(self, user_repository: UserRepository, redis: Redis):
        self._repo = user_repository
        self._redis = redis

    async def sign_in(self, username: str, password: str) -> tuple[UserProfile, str]:
        """Authenticate user and create a Redis-backed session."""
        user = await self._repo.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthorized", "message_key": "error.unauthorized"},
            )

        session_id = os.urandom(32).hex()
        session_data = {
            "user_id": str(user.id),
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "created_at": time.time(),
            "last_activity": time.time(),
        }
        await self._redis.set(
            f"session:{session_id}",
            json.dumps(session_data),
            ex=8 * 3600,
        )

        profile = UserProfile(
            id=str(user.id),
            username=user.username,
            display_name=user.display_name,
            role=user.role,
        )
        return profile, session_id

    async def sign_out(self, session_id: str) -> None:
        """Delete the session from Redis."""
        await self._redis.delete(f"session:{session_id}")

    async def get_me(self, session_id: str) -> UserProfile:
        """Return the user profile for the given session."""
        raw = await self._redis.get(f"session:{session_id}")
        if raw is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthorized", "message_key": "error.unauthorized"},
            )
        data = json.loads(raw)
        return UserProfile(
            id=data["user_id"],
            username=data["username"],
            display_name=data["display_name"],
            role=data["role"],
        )
