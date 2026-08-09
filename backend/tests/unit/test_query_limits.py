"""Configured prompt-length discovery contract."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.query import router
from app.core.config import get_settings
from app.db.models.enums import Permission
from tests.unit.permission_test_helpers import use_test_session_current_role

AUTHORIZED_SESSION = {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "prompt-limit-user",
    "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "role_name": "Prompt submitter",
    "permissions": [Permission.QUERY_SUBMIT.value],
}


def _limits_app(session: dict | None) -> FastAPI:
    class SessionInjectionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.session = session
            return await call_next(request)

    async def sanitized_http_exception_handler(_request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    app = FastAPI()
    use_test_session_current_role(app)
    app.add_middleware(SessionInjectionMiddleware)
    app.add_exception_handler(HTTPException, sanitized_http_exception_handler)
    app.include_router(router, prefix="/api/v1")
    return app


def test_max_question_length_loads_non_default_positive_integer(monkeypatch):
    monkeypatch.setenv("MAX_QUESTION_LENGTH", "37")
    get_settings.cache_clear()

    assert get_settings().MAX_QUESTION_LENGTH == 37


@pytest.mark.parametrize("configured_limit", ["0", "-1"])
def test_non_positive_max_question_length_is_rejected(monkeypatch, configured_limit):
    monkeypatch.setenv("MAX_QUESTION_LENGTH", configured_limit)
    get_settings.cache_clear()

    with pytest.raises(ValidationError, match="MAX_QUESTION_LENGTH must be positive"):
        get_settings()


@pytest.mark.parametrize(
    ("session", "expected_status", "expected_body"),
    [
        (
            AUTHORIZED_SESSION,
            200,
            {"max_question_length": 37},
        ),
        (
            {**AUTHORIZED_SESSION, "permissions": [Permission.QUERY_HISTORY_VIEW.value]},
            403,
            {"error": "forbidden", "message_key": "error.forbidden"},
        ),
        (
            None,
            401,
            {"error": "unauthorized", "message_key": "error.unauthorized"},
        ),
    ],
)
@pytest.mark.asyncio
async def test_query_limits_exposes_only_the_authorized_configured_limit(
    monkeypatch,
    session,
    expected_status,
    expected_body,
):
    monkeypatch.setenv("MAX_QUESTION_LENGTH", "37")
    get_settings.cache_clear()
    app = _limits_app(session)

    with patch(
        "app.api.dependencies.permissions.AuditService.log",
        new_callable=AsyncMock,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/query/limits")

    assert response.status_code == expected_status
    assert response.json() == expected_body
