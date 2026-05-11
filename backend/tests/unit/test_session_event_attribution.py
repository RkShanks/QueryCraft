"""T-250: Verify user_id attribution in session events and diagnostic logs.

FR-027 mandates that every persisted record and diagnostic log entry carries
a user identifier. This test asserts that the session middleware binds the
user_id into the structlog context so subsequent log entries include it.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import SessionMiddleware


class TestSessionEventAttribution:
    """Unit tests for user_id presence in session context and logs."""

    @pytest.fixture
    def mock_app(self):
        async def app(scope, receive, send):
            response_start = {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"application/json"]],
            }
            await send(response_start)
            await send({"type": "http.response.body", "body": b"{}"})
        return app

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock()
        redis.set = AsyncMock()
        redis.delete = AsyncMock()
        return redis

    @pytest.fixture
    def session_middleware(self, mock_app):
        return SessionMiddleware(
            mock_app,
            redis_url="redis://localhost:6379/0",
            idle_timeout_hours=8,
        )

    @pytest.mark.asyncio
    async def test_user_id_bound_to_log_context(self, session_middleware, mock_redis):
        """When a valid session is present, user_id is bound to log context."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        import time
        now = time.time()
        session_data = {
            "user_id": user_id,
            "username": "admin",
            "display_name": "Admin",
            "role": "admin",
            "created_at": now,
            "last_activity": now,
        }
        mock_redis.get.return_value = json.dumps(session_data)
        session_middleware._get_redis = AsyncMock(return_value=mock_redis)

        bound_vars = {}
        with patch("structlog.contextvars.bind_contextvars") as mock_bind:
            mock_bind.side_effect = lambda **kwargs: bound_vars.update(kwargs)

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [[b"cookie", b"session_id=valid-session"]],
                "state": {},
            }

            async def receive():
                return {"type": "http.request"}

            messages = []
            async def send(message):
                messages.append(message)

            await session_middleware(scope, receive, send)

        assert "user_id" in bound_vars, "Expected bind_contextvars to be called with user_id"
        assert bound_vars["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_no_user_id_for_anonymous(self, session_middleware, mock_redis):
        """When no session is present, user_id is NOT bound to log context."""
        mock_redis.get.return_value = None
        session_middleware._get_redis = AsyncMock(return_value=mock_redis)

        bound_calls = []
        with patch("structlog.contextvars.bind_contextvars") as mock_bind:
            mock_bind.side_effect = lambda **kwargs: bound_calls.append(kwargs)

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [],
                "state": {},
            }

            async def receive():
                return {"type": "http.request"}

            messages = []
            async def send(message):
                messages.append(message)

            await session_middleware(scope, receive, send)

        assert not any("user_id" in call for call in bound_calls), (
            "Did not expect user_id in bound context for anonymous request"
        )
