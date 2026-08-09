"""Public submit boundaries for the configured canonical prompt length."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request

from app.api.v1.query import submit_question
from app.core.config import get_settings
from app.db.models.enums import Permission
from app.schemas.query import QueryResult, SubmitQuestionRequest

CONNECTION_ID = "550e8400-e29b-41d4-a716-446655440001"
AUTHORIZED_SESSION = {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "prompt-boundary-user",
    "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "role_name": "Prompt submitter",
    "permissions": [Permission.QUERY_SUBMIT.value],
}


class QueryPipelineBoundary:
    """Record only value-safe facts when the router enters query processing."""

    def __init__(self) -> None:
        self.submitted_lengths: list[int] = []
        self.received_canonical_text: list[bool] = []

    async def submit_question(self, *, question: str, **_kwargs) -> QueryResult:
        self.submitted_lengths.append(len(question))
        self.received_canonical_text.append(question == question.strip())
        return QueryResult(
            attempt_id="550e8400-e29b-41d4-a716-446655440010",
            question=question,
            generated_sql="SELECT 1",
            columns=[],
            rows=[],
            row_count=0,
            attempt_number=1,
            is_last_auto_retry=False,
        )


@pytest.mark.parametrize(
    ("question", "expected_status", "expected_pipeline_lengths"),
    [
        pytest.param("x" * 3, 200, [3], id="limit-minus-one"),
        pytest.param("x" * 4, 200, [4], id="limit"),
        pytest.param("x" * 5, 400, [], id="limit-plus-one"),
        pytest.param(" \t" + "x" * 4 + "\n", 200, [4], id="trim-before-count"),
        pytest.param("س" * 4, 200, [4], id="arabic-code-points"),
        pytest.param("😀" * 4, 200, [4], id="non-bmp-code-points"),
        pytest.param("😀" * 5, 400, [], id="non-bmp-over-limit"),
    ],
)
@pytest.mark.asyncio
async def test_submit_uses_configured_trimmed_unicode_code_point_boundary(
    monkeypatch,
    question,
    expected_status,
    expected_pipeline_lengths,
):
    monkeypatch.setenv("MAX_QUESTION_LENGTH", "4")
    get_settings.cache_clear()
    db = AsyncMock()
    redis = AsyncMock()
    pipeline = QueryPipelineBoundary()
    request = MagicMock(spec=Request)
    request.state.session_id = "configured-limit-session"
    req = SubmitQuestionRequest(question=question, connection_id=CONNECTION_ID)

    with patch(
        "app.api.v1.query._build_query_service_for_connection",
        new=AsyncMock(return_value=pipeline),
    ):
        if expected_status == 400:
            with pytest.raises(HTTPException) as exc_info:
                await submit_question(
                    request=request,
                    _session=AUTHORIZED_SESSION,
                    req=req,
                    user_id=AUTHORIZED_SESSION["user_id"],
                    db=db,
                    redis=redis,
                )
            response_status = exc_info.value.status_code
            response_body = exc_info.value.detail
        else:
            response = await submit_question(
                request=request,
                _session=AUTHORIZED_SESSION,
                req=req,
                user_id=AUTHORIZED_SESSION["user_id"],
                db=db,
                redis=redis,
            )
            response_status = 200
            response_body = response.model_dump()

    assert response_status == expected_status
    assert pipeline.submitted_lengths == expected_pipeline_lengths
    assert all(pipeline.received_canonical_text)
    if expected_status == 400:
        assert response_body == {
            "error": "validation",
            "message_key": "error.validation.questionTooLong",
        }
        assert db.method_calls == []
        assert redis.method_calls == []
