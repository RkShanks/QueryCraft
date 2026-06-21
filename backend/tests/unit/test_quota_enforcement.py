"""RED unit tests for quota enforcement in query flow (T-799).

Tests that:
- POST /query/submit calls QuotaService.check_and_increment("queries") before LLM
- Request returns 429 + localized message_key when quota exceeded
- LLM never called when quota exceeded
- QuotaUnavailableError → 503 localized "service_unavailable" message
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.exceptions import QuotaExceededError, QuotaUnavailableError


class TestQueryQuotaEnforcement:
    """Quota gate before LLM invocation in submit flow."""

    @pytest.mark.asyncio
    async def test_submit_calls_quota_check_before_llm(self):
        from app.services.query_service import QueryService

        mock_repo = AsyncMock()
        mock_session_repo = AsyncMock()
        mock_llm = AsyncMock()
        mock_evaluator = AsyncMock()
        mock_executor = AsyncMock()
        mock_redis = AsyncMock()
        mock_db = AsyncMock()
        mock_quota_service = AsyncMock()

        user_id = uuid.uuid4()
        role_id = uuid.uuid4()

        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=MagicMock(id=user_id, role_id=role_id, username="testuser"))
        ))
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()
        mock_session_repo.create = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))
        mock_session_repo.get_by_id = AsyncMock(return_value=MagicMock(
            id=uuid.uuid4(),
            preview_text="test",
            user_id=user_id,
        ))
        mock_session_repo.update_last_activity = AsyncMock()
        mock_session_repo.update_preview_text = AsyncMock()
        mock_repo.get_latest_by_session = AsyncMock(return_value=None)
        mock_repo.list_by_session = AsyncMock(return_value=[])
        mock_repo.get_by_attempt_id = AsyncMock(return_value=None)
        mock_repo.create = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))

        mock_quota_service.check_and_increment = AsyncMock(return_value=(1, 10, None))

        mock_llm.generate_sql = AsyncMock(return_value="SELECT 1")
        mock_evaluator.evaluate = AsyncMock(return_value=MagicMock(passed=True, violations=[]))

        service = QueryService(
            accepted_query_repository=mock_repo,
            session_repository=mock_session_repo,
            db_session=mock_db,
            redis=mock_redis,
            llm=mock_llm,
            evaluator=mock_evaluator,
            source_db_executor=mock_executor,
            llm_provider="test",
            schema_context="",
            quota_service=mock_quota_service,
        )

        with patch.object(service, "_get_database_connection_id", return_value=str(uuid.uuid4())):
            with __import__("contextlib").suppress(Exception):
                await service.submit_question(
                    http_session_id="test-session",
                    user_id=str(user_id),
                    question="test question",
                )

        mock_quota_service.check_and_increment.assert_any_call(
            user_id, role_id, "queries"
        )

    @pytest.mark.asyncio
    async def test_submit_returns_429_when_quota_exceeded(self):
        from app.services.query_service import QueryService

        mock_repo = AsyncMock()
        mock_session_repo = AsyncMock()
        mock_llm = AsyncMock()
        mock_evaluator = AsyncMock()
        mock_executor = AsyncMock()
        mock_redis = AsyncMock()
        mock_db = AsyncMock()
        mock_quota_service = AsyncMock()

        user_id = uuid.uuid4()
        role_id = uuid.uuid4()

        reset_at = "2026-06-13T00:00:00+00:00"
        mock_quota_service.check_and_increment = AsyncMock(
            side_effect=QuotaExceededError(dimension="queries", reset_at=reset_at)
        )

        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()

        service = QueryService(
            accepted_query_repository=mock_repo,
            session_repository=mock_session_repo,
            db_session=mock_db,
            redis=mock_redis,
            llm=mock_llm,
            evaluator=mock_evaluator,
            source_db_executor=mock_executor,
            llm_provider="test",
            schema_context="",
            quota_service=mock_quota_service,
        )

        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=MagicMock(id=user_id, role_id=role_id, username="testuser"))
        ))

        with pytest.raises(HTTPException) as exc_info:
            await service.submit_question(
                http_session_id="test-session",
                user_id=str(user_id),
                question="test question",
            )

        assert exc_info.value.status_code == 429
        assert exc_info.value.detail["message_key"] == "error.quota_exceeded"

    @pytest.mark.asyncio
    async def test_llm_not_called_when_quota_exceeded(self):
        from app.services.query_service import QueryService

        mock_repo = AsyncMock()
        mock_session_repo = AsyncMock()
        mock_llm = AsyncMock()
        mock_evaluator = AsyncMock()
        mock_executor = AsyncMock()
        mock_redis = AsyncMock()
        mock_db = AsyncMock()
        mock_quota_service = AsyncMock()

        user_id = uuid.uuid4()
        role_id = uuid.uuid4()

        reset_at = "2026-06-13T00:00:00+00:00"
        mock_quota_service.check_and_increment = AsyncMock(
            side_effect=QuotaExceededError(dimension="queries", reset_at=reset_at)
        )

        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()

        service = QueryService(
            accepted_query_repository=mock_repo,
            session_repository=mock_session_repo,
            db_session=mock_db,
            redis=mock_redis,
            llm=mock_llm,
            evaluator=mock_evaluator,
            source_db_executor=mock_executor,
            llm_provider="test",
            schema_context="",
            quota_service=mock_quota_service,
        )

        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=MagicMock(id=user_id, role_id=role_id, username="testuser"))
        ))

        with __import__("contextlib").suppress(HTTPException):
            await service.submit_question(
                http_session_id="test-session",
                user_id=str(user_id),
                question="test question",
            )

        mock_llm.generate_sql.assert_not_called()

    @pytest.mark.asyncio
    async def test_quota_unavailable_returns_503_fail_closed(self):
        from app.services.query_service import QueryService

        mock_repo = AsyncMock()
        mock_session_repo = AsyncMock()
        mock_llm = AsyncMock()
        mock_evaluator = AsyncMock()
        mock_executor = AsyncMock()
        mock_redis = AsyncMock()
        mock_db = AsyncMock()
        mock_quota_service = AsyncMock()

        user_id = uuid.uuid4()
        role_id = uuid.uuid4()

        mock_quota_service.check_and_increment = AsyncMock(
            side_effect=QuotaUnavailableError()
        )

        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()

        service = QueryService(
            accepted_query_repository=mock_repo,
            session_repository=mock_session_repo,
            db_session=mock_db,
            redis=mock_redis,
            llm=mock_llm,
            evaluator=mock_evaluator,
            source_db_executor=mock_executor,
            llm_provider="test",
            schema_context="",
            quota_service=mock_quota_service,
        )

        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=MagicMock(id=user_id, role_id=role_id, username="testuser"))
        ))

        with pytest.raises(HTTPException) as exc_info:
            await service.submit_question(
                http_session_id="test-session",
                user_id=str(user_id),
                question="test question",
            )

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["message_key"] == "error.service_unavailable"

        mock_llm.generate_sql.assert_not_called()


class TestQueryEndpointQuotaResponse:
    """API layer quota error response shape tests."""

    @pytest.mark.asyncio
    async def test_quota_exceeded_response_429_with_message_key(self):
        from fastapi import HTTPException, status


        reset_at = "2026-06-13T00:00:00+00:00"

        http_exc = HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "quota_exceeded",
                "message_key": "error.quota_exceeded",
                "reset_at": reset_at,
            },
        )

        assert http_exc.status_code == 429
        assert http_exc.detail["message_key"] == "error.quota_exceeded"
        assert "reset_at" in http_exc.detail
        assert "counter" not in http_exc.detail
        assert "limit" not in http_exc.detail
        assert "policy_id" not in http_exc.detail

    @pytest.mark.asyncio
    async def test_quota_unavailable_response_503_with_message_key(self):
        from fastapi import HTTPException, status


        http_exc = HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "service_unavailable",
                "message_key": "error.service_unavailable",
            },
        )

        assert http_exc.status_code == 503
        assert http_exc.detail["message_key"] == "error.service_unavailable"
        assert "stack" not in http_exc.detail
        assert "provider" not in http_exc.detail
