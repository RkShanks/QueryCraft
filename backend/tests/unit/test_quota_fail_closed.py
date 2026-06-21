"""RED security test for fail-closed behavior (T-806).

Mock Redis to be completely unreachable; assert quota-gated endpoints
(submit, execute) return 503 with message_key="error.service_unavailable"
and no request proceeds to LLM or DB.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core.exceptions import QuotaUnavailableError
from app.services.query_service import QueryService


class TestQuotaFailClosed:
    @pytest.mark.asyncio
    async def test_submit_returns_503_when_redis_unreachable(self):
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

        mock_quota_service.check_and_increment = AsyncMock(side_effect=QuotaUnavailableError())

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

        mock_db.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=MagicMock(id=user_id, role_id=role_id, username="testuser"))
            )
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.submit_question(
                http_session_id="test-session",
                user_id=str(user_id),
                question="test question",
            )

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["message_key"] == "error.service_unavailable"
        mock_llm.generate_sql.assert_not_called()

    @pytest.mark.asyncio
    async def test_execution_blocked_when_redis_unreachable(self):
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
        session_id = uuid.uuid4()

        call_count = 0

        async def _check_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (1, 10, None)
            raise QuotaUnavailableError()

        mock_quota_service.check_and_increment = AsyncMock(side_effect=_check_side_effect)

        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()

        mock_llm.generate_sql = AsyncMock(return_value="SELECT 1")
        mock_evaluator.evaluate = AsyncMock(return_value=MagicMock(passed=True, violations=[]))

        mock_session_repo.create = AsyncMock(return_value=MagicMock(id=session_id))
        mock_session_repo.get_by_id = AsyncMock(
            return_value=MagicMock(
                id=session_id,
                preview_text="test",
                user_id=user_id,
            )
        )
        mock_session_repo.update_last_activity = AsyncMock()
        mock_session_repo.update_preview_text = AsyncMock()

        mock_repo.get_latest_by_session = AsyncMock(return_value=None)
        mock_repo.list_by_session = AsyncMock(return_value=[])
        mock_repo.get_by_attempt_id = AsyncMock(return_value=None)
        mock_repo.create = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))

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

        mock_db.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=MagicMock(id=user_id, role_id=role_id, username="testuser"))
            )
        )

        from unittest.mock import patch

        with patch.object(service, "_get_database_connection_id", return_value=str(uuid.uuid4())):
            with pytest.raises(HTTPException) as exc_info:
                await service.submit_question(
                    http_session_id="test-session",
                    user_id=str(user_id),
                    question="test question",
                    chat_session_id=str(session_id),
                )

        assert exc_info.value.status_code == 503
        mock_executor.execute.assert_not_called()
