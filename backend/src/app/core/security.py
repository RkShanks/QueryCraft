"""Session middleware, Origin validation, and password hashing (security.py)."""

import json
import os
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against an Argon2id hash."""
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


class SessionMiddleware:
    """Redis-backed server-side session middleware.

    Reads session_id from HttpOnly cookie, loads session from Redis,
    validates idle timeout, and attaches session data to request.state.
    """

    COOKIE_NAME = "session_id"

    def __init__(self, app, redis_url: str, idle_timeout_hours: int = 8, secure: bool = True):
        self.app = app
        self.redis_url = redis_url
        self.idle_timeout_hours = idle_timeout_hours
        self.secure = secure
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            from redis.asyncio import Redis

            self._redis = Redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        from starlette.requests import Request

        request = Request(scope, receive)
        session_id = request.cookies.get(self.COOKIE_NAME)

        # Attach empty session by default
        scope.setdefault("state", {})
        request.state.session = None
        request.state.session_id = None

        if session_id:
            redis = await self._get_redis()
            session_data = await redis.get(f"session:{session_id}")
            if session_data:
                session = json.loads(session_data)
                # Check idle timeout
                last_activity = session.get("last_activity", 0)
                idle_limit = self.idle_timeout_hours * 3600
                if time.time() - last_activity > idle_limit:
                    # Session expired
                    await redis.delete(f"session:{session_id}")
                else:
                    # Update last_activity
                    session["last_activity"] = time.time()
                    await redis.set(
                        f"session:{session_id}",
                        json.dumps(session),
                        ex=self.idle_timeout_hours * 3600,
                    )
                    request.state.session = session
                    request.state.session_id = session_id

        await self.app(scope, receive, send)

    @classmethod
    async def create_session(cls, redis, user_data: dict, idle_timeout_hours: int = 8) -> str:
        """Create a new session in Redis and return the session_id."""
        session_id = os.urandom(32).hex()
        session = {
            **user_data,
            "created_at": time.time(),
            "last_activity": time.time(),
        }
        await redis.set(
            f"session:{session_id}",
            json.dumps(session),
            ex=idle_timeout_hours * 3600,
        )
        return session_id

    @classmethod
    async def delete_session(cls, redis, session_id: str) -> None:
        """Delete a session from Redis."""
        await redis.delete(f"session:{session_id}")

    @classmethod
    def set_cookie(cls, response, session_id: str, secure: bool = True) -> None:
        """Set session cookie with security flags."""
        response.set_cookie(
            key=cls.COOKIE_NAME,
            value=session_id,
            httponly=True,
            secure=secure,
            samesite="strict",
            path="/",
        )

    @classmethod
    def delete_cookie(cls, response) -> None:
        """Delete the session cookie."""
        response.delete_cookie(key=cls.COOKIE_NAME, path="/")


class OriginValidatorMiddleware:
    """Validates Origin header on state-changing requests (POST/PUT/PATCH/DELETE).

    GET/HEAD/OPTIONS bypass the check (R-007).
    """

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    def __init__(self, app, allowed_origins: list[str]):
        self.app = app
        self.allowed_origins = set(allowed_origins)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from starlette.requests import Request
        from starlette.responses import JSONResponse

        request = Request(scope, receive)
        method = request.method.upper()

        if method not in self.SAFE_METHODS:
            origin = request.headers.get("origin")
            if not origin or origin not in self.allowed_origins:
                response = JSONResponse(
                    status_code=403,
                    content={
                        "error": "forbidden",
                        "message_key": "error.forbidden",
                    },
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
