"""Endpoint regression test: POST /query/submit forwards chat session_id (T-348).

Proves the API endpoint passes request-body session_id to
QueryService.submit_question as chat_session_id, and passes the HTTP
session id as http_session_id.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.query import SubmitQuestionRequest


class MockRequest:
    """Minimal ASGI request stand-in for endpoint unit tests."""

    def __init__(self, session, session_id):
        self.state = MagicMock()
        self.state.session = session
        self.state.session_id = session_id


@pytest.mark.asyncio
async def test_submit_endpoint_forwards_chat_session_id():
    """Endpoint must pass req.session_id as chat_session_id to service."""
    mock_service = AsyncMock()
    mock_result = MagicMock()
    mock_result.kind = "result"
    mock_service.submit_question.return_value = mock_result

    from app.api.v1.query import submit_question

    request = MockRequest(session={"user_id": "550e8400-e29b-41d4-a716-446655440000"}, session_id="http-sess-1")
    req = SubmitQuestionRequest(question="Follow-up", session_id="550e8400-e29b-41d4-a716-446655440002")

    result = await submit_question(request=request, req=req, service=mock_service)

    mock_service.submit_question.assert_awaited_once()
    call_kwargs = mock_service.submit_question.await_args.kwargs
    assert call_kwargs["http_session_id"] == "http-sess-1"
    assert call_kwargs["user_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert call_kwargs["question"] == "Follow-up"
    assert call_kwargs["chat_session_id"] == "550e8400-e29b-41d4-a716-446655440002"
    assert result.kind == "result"


@pytest.mark.asyncio
async def test_submit_endpoint_forwards_none_chat_session_id_for_new_chat():
    """Endpoint must pass chat_session_id=None when body omits session_id."""
    mock_service = AsyncMock()
    mock_result = MagicMock()
    mock_result.kind = "result"
    mock_service.submit_question.return_value = mock_result

    from app.api.v1.query import submit_question

    request = MockRequest(session={"user_id": "550e8400-e29b-41d4-a716-446655440000"}, session_id="http-sess-1")
    req = SubmitQuestionRequest(question="New question")

    result = await submit_question(request=request, req=req, service=mock_service)

    mock_service.submit_question.assert_awaited_once()
    call_kwargs = mock_service.submit_question.await_args.kwargs
    assert call_kwargs["chat_session_id"] is None
    assert result.kind == "result"
