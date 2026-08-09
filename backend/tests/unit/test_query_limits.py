"""Configured prompt-length discovery contract."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request
from pydantic import ValidationError

from app.api.v1.query import get_query_limits, router
from app.core.config import get_settings
from app.db.models.enums import Permission
from tests.unit.permission_test_helpers import evaluate_permission_dependency

AUTHORIZED_SESSION = {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "prompt-limit-user",
    "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "role_name": "Prompt submitter",
    "permissions": [Permission.QUERY_SUBMIT.value],
}


def _limits_permission_dependency():
    route = next(route for route in router.routes if route.path == "/query/limits")
    assert route.methods == {"GET"}
    return route.dependant.dependencies[0].call


def _request_with_session(session: dict | None) -> Request:
    request = MagicMock(spec=Request)
    request.state.session = session
    return request


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


@pytest.mark.asyncio
async def test_query_limits_exposes_only_the_authorized_configured_limit(monkeypatch):
    monkeypatch.setenv("MAX_QUESTION_LENGTH", "37")
    get_settings.cache_clear()
    request = _request_with_session(AUTHORIZED_SESSION)

    session = await evaluate_permission_dependency(
        _limits_permission_dependency(),
        request,
    )
    response = await get_query_limits(_session=session)

    assert response.model_dump() == {"max_question_length": 37}


@pytest.mark.parametrize(
    ("session", "expected_status", "expected_body"),
    [
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
async def test_query_limits_rejects_callers_without_submit_permission(
    session,
    expected_status,
    expected_body,
):
    request = _request_with_session(session)

    with pytest.raises(HTTPException) as exc_info:
        await evaluate_permission_dependency(
            _limits_permission_dependency(),
            request,
        )

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail == expected_body
