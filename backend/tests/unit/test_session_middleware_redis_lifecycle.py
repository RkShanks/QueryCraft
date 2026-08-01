"""F-002: SessionMiddleware caches Redis client and closes on shutdown."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.security import SessionMiddleware


def _make_scope_with_cookie():
    """Build a minimal ASGI HTTP scope with a session_id cookie."""
    cookie_header = b"cookie", b"session_id=test-session"
    return {
        "type": "http",
        "method": "GET",
        "headers": [cookie_header],
        "state": {},
    }


@pytest.mark.asyncio
async def test_session_middleware_caches_redis_client():
    """Redis.from_url should be called exactly once for many requests."""
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)

    call_count = 0

    def fake_from_url(url, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_redis

    with patch("redis.asyncio.Redis.from_url", side_effect=fake_from_url):
        middleware = SessionMiddleware(
            app=lambda s, r, se: asyncio.sleep(0),
            redis_url="redis://localhost:6379/0",
        )
        # Simulate 5 sequential requests with a session cookie
        for _ in range(5):
            scope = _make_scope_with_cookie()
            await middleware(scope, None, None)

    assert call_count == 1, f"Expected 1 Redis.from_url call, got {call_count}"


@pytest.mark.asyncio
async def test_session_middleware_aclose_closes_redis():
    """Calling aclose() should close the cached Redis client."""
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.aclose = AsyncMock()

    with patch("redis.asyncio.Redis.from_url", return_value=mock_redis):
        middleware = SessionMiddleware(
            app=lambda s, r, se: asyncio.sleep(0),
            redis_url="redis://localhost:6379/0",
        )
        scope = _make_scope_with_cookie()
        await middleware(scope, None, None)

    await middleware.aclose()
    mock_redis.aclose.assert_awaited_once()
    assert middleware._redis is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "redis_response",
    [
        RedisConnectionError("private redis location"),
        RedisTimeoutError("private timeout detail"),
        ResponseError("private command detail"),
        "not-json",
        "[]",
    ],
)
async def test_invalid_session_dependency_state_returns_sanitized_503(redis_response):
    """Redis failures and corrupt session state share one fail-closed contract."""
    downstream_app = AsyncMock()
    mock_redis = MagicMock()
    if isinstance(redis_response, BaseException):
        mock_redis.get = AsyncMock(side_effect=redis_response)
    else:
        mock_redis.get = AsyncMock(return_value=redis_response)
    middleware = SessionMiddleware(
        app=downstream_app,
        redis_url="redis://dependency.invalid:6379/0",
    )
    sent_messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent_messages.append(message)

    with patch("redis.asyncio.Redis.from_url", return_value=mock_redis):
        await middleware(_make_scope_with_cookie(), receive, send)

    downstream_app.assert_not_awaited()
    response_start = next(message for message in sent_messages if message["type"] == "http.response.start")
    response_body = next(message for message in sent_messages if message["type"] == "http.response.body")
    assert response_start["status"] == 503
    assert json.loads(response_body["body"]) == {
        "error": "service_unavailable",
        "message_key": "error.service_unavailable",
    }
    assert b"private" not in response_body["body"]
