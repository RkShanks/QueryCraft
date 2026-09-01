"""F-002: SessionMiddleware caches Redis client and closes on shutdown."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.security import SessionMiddleware

_USER_ID = "550e8400-e29b-41d4-a716-446655440000"
_OTHER_USER_ID = "550e8400-e29b-41d4-a716-446655440001"
_ROLE_ID = "550e8400-e29b-41d4-a716-446655441000"


def _valid_session_record() -> dict:
    return {
        "user_id": _USER_ID,
        "username": "admin",
        "display_name": "Admin",
        "role": "admin",
        "role_id": _ROLE_ID,
        "role_name": "Admin",
        "permissions": ["query.submit"],
        "auth_provider": "local",
        "subject_id": "admin",
        "created_at": 1000.0,
        "last_activity": 1000.0,
    }


def _session_with(**replacement) -> dict:
    session = _valid_session_record()
    session.update(replacement)
    return session


_CORRUPT_SESSION_DOCUMENTS = [
    pytest.param({key: val for key, val in _valid_session_record().items() if key != "user_id"}, id="missing-user-id"),
    pytest.param(_session_with(user_id="not-a-uuid"), id="invalid-user-id"),
    pytest.param(_session_with(user_id=_USER_ID.upper()), id="noncanonical-user-id"),
    pytest.param(_session_with(username=[]), id="username-list"),
    pytest.param(_session_with(permissions="query.submit"), id="permissions-scalar"),
    pytest.param(_session_with(permissions=["query.submit", {"nested": "permission"}]), id="permissions-nested"),
    pytest.param(_session_with(role={}), id="role-object"),
    pytest.param(_session_with(role_id=[]), id="role-id-list"),
    pytest.param(_session_with(role_name=4), id="role-name-scalar"),
    pytest.param(_session_with(auth_provider=False), id="provider-boolean"),
    pytest.param(_session_with(auth_provider="oauth"), id="provider-unknown"),
    pytest.param(_session_with(created_at="1000"), id="created-at-string"),
    pytest.param(_session_with(last_activity=None), id="last-activity-null"),
    pytest.param(_session_with(user_id=_OTHER_USER_ID), id="index-owner-mismatch"),
    pytest.param({**_valid_session_record(), "unexpected": "field"}, id="unknown-field"),
    pytest.param([], id="document-list"),
    pytest.param("session", id="document-scalar"),
    pytest.param(None, id="document-null"),
]


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
    mock_redis.mget = AsyncMock(return_value=[None, None])
    mock_redis.eval = AsyncMock(return_value=None)

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
    mock_redis.mget = AsyncMock(return_value=[None, None])
    mock_redis.eval = AsyncMock(return_value=None)
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
async def test_session_middleware_failed_close_retains_client_for_retry():
    """A failed close remains registered until a later close succeeds."""
    mock_redis = MagicMock()
    mock_redis.aclose = AsyncMock(side_effect=[RuntimeError("private redis detail"), None])
    middleware = SessionMiddleware(
        app=lambda s, r, se: asyncio.sleep(0),
        redis_url="redis://dependency.invalid:6379/0",
    )
    middleware._redis = mock_redis

    with pytest.raises(RuntimeError, match="private redis detail"):
        await middleware.aclose()

    assert middleware._redis is mock_redis
    await middleware.aclose()
    assert mock_redis.aclose.await_count == 2
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
        mock_redis.mget = AsyncMock(side_effect=redis_response)
        mock_redis.eval = AsyncMock(side_effect=redis_response)
    else:
        mock_redis.mget = AsyncMock(return_value=[redis_response, None])
        mock_redis.eval = AsyncMock(return_value=redis_response)
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


@pytest.mark.asyncio
@pytest.mark.parametrize("session_document", _CORRUPT_SESSION_DOCUMENTS)
async def test_semantically_corrupt_session_returns_sanitized_503(session_document):
    """IS-GAP-021: invalid authentication state never reaches the application."""
    downstream_app = AsyncMock()
    raw_session = json.dumps(session_document)
    mock_redis = MagicMock()
    mock_redis.mget = AsyncMock(return_value=[raw_session, _USER_ID])
    mock_redis.eval = AsyncMock(return_value=raw_session)
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
    assert raw_session.encode() not in response_body["body"]


@pytest.mark.asyncio
async def test_session_redis_outage_does_not_run_corruption_cleanup():
    """Dependency failure remains distinct from owned-record corruption."""
    downstream_app = AsyncMock()
    mock_redis = MagicMock()
    dependency_error = RedisConnectionError("private dependency location")
    mock_redis.mget = AsyncMock(side_effect=dependency_error)
    mock_redis.eval = AsyncMock(side_effect=dependency_error)
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
    mock_redis.eval.assert_not_awaited()
    response_body = next(message for message in sent_messages if message["type"] == "http.response.body")
    assert json.loads(response_body["body"])["error"] == "service_unavailable"
