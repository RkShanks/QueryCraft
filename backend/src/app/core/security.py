"""Session middleware, Origin validation, and password hashing (security.py)."""

import json
import os
import time

import structlog
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from redis.exceptions import RedisError

from app.core.exceptions import SessionRecordInvalid
from app.core.session_record import parse_session_record
from app.repositories.session_repository import (
    IndexedSessionCreateRequest,
    IndexedSessionRefreshRequest,
    SessionRepository,
)

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
    OPERATIONAL_PROBE_PATHS = frozenset({"/health", "/ready"})
    _instances: list["SessionMiddleware"] = []

    def __init__(self, app, redis_url: str, idle_timeout_hours: int = 8, secure: bool = True):
        self.app = app
        self.redis_url = redis_url
        self.idle_timeout_hours = idle_timeout_hours
        self.secure = secure
        self._redis = None
        SessionMiddleware._instances.append(self)

    async def _get_redis(self):
        from redis.asyncio import Redis

        if self._redis is None:
            self._redis = Redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def aclose(self) -> None:
        """Close the cached Redis client and reset the cache."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def _load_session(self, session_id: str) -> dict | None:
        redis = await self._get_redis()
        idle_limit = self.idle_timeout_hours * 3600
        for _load_attempt in range(2):
            stored_session = await SessionRepository.read_indexed_session(redis, session_id)
            if stored_session.session_json is None:
                return None
            try:
                parse_session_record(stored_session.session_json, stored_session.indexed_user_id)
            except SessionRecordInvalid:
                await SessionRepository.delete_corrupt_indexed_session(
                    redis,
                    session_id,
                    stored_session.session_json,
                )
                raise
            refresh_result = await SessionRepository.refresh_indexed_session_state(
                redis,
                IndexedSessionRefreshRequest(
                    session_id=session_id,
                    now=time.time(),
                    ttl_seconds=idle_limit,
                    expected_session_json=stored_session.session_json,
                ),
            )
            if refresh_result.concurrent_replacement:
                continue
            if refresh_result.session_json is None:
                return None
            return parse_session_record(refresh_result.session_json, stored_session.indexed_user_id)
        raise SessionRecordInvalid()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path") in self.OPERATIONAL_PROBE_PATHS:
            await self.app(scope, receive, send)
            return

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
            try:
                session = await self._load_session(session_id)
            except (RedisError, OSError, SessionRecordInvalid):
                from starlette.responses import JSONResponse

                response = JSONResponse(
                    status_code=503,
                    content={
                        "error": "service_unavailable",
                        "message_key": "error.service_unavailable",
                    },
                )
                await response(scope, receive, send)
                return
            if session is not None:
                request.state.session = session
                request.state.session_id = session_id
                structlog.contextvars.bind_contextvars(user_id=session.get("user_id"))

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
        user_id = str(session["user_id"])
        await SessionRepository.create_indexed_session(
            redis,
            IndexedSessionCreateRequest(
                user_id=user_id,
                session_id=session_id,
                session_json=json.dumps(session),
                created_at=float(session["created_at"]),
                max_sessions=0,
                ttl_seconds=idle_timeout_hours * 3600,
            ),
        )
        return session_id

    @classmethod
    async def delete_session(cls, redis, session_id: str) -> None:
        """Delete a session from Redis."""
        await SessionRepository.delete_indexed_session(redis, session_id)

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
    SAML ACS POST bypasses the check (IdP callbacks have no same-origin Origin).
    """

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    SAML_ACS_PATH = "/api/v1/auth/sso/saml/callback"

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
            path = scope.get("path", "")
            if path != self.SAML_ACS_PATH:
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
