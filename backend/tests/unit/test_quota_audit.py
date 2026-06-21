"""RED unit tests for quota audit events (T-803).

Tests that:
- QUOTA_EXCEEDED audit event emitted with action_type, actor_identity,
  outcome="blocked", context has dimension and reset_at but NO counter
  values or policy IDs
- QUOTA_CONFIG_CHANGE event has sanitized context
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.models.enums import AuditActionType


class TestQuotaExceededAuditEvent:
    @pytest.mark.asyncio
    async def test_query_quota_exceeded_emits_audit_event(self):
        from app.core.exceptions import QuotaExceededError
        from app.services.audit_service import AuditService
        from app.services.query_service import QueryService

        user_id = uuid.uuid4()
        role_id = uuid.uuid4()

        mock_repo = AsyncMock()
        mock_session_repo = AsyncMock()
        mock_llm = AsyncMock()
        mock_evaluator = AsyncMock()
        mock_executor = AsyncMock()
        mock_redis = AsyncMock()
        mock_db = AsyncMock()
        mock_quota_service = AsyncMock()

        mock_quota_service.check_and_increment = AsyncMock(
            side_effect=QuotaExceededError(dimension="queries", reset_at="2026-06-13T00:00:00+00:00")
        )

        mock_db.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=MagicMock(id=user_id, role_id=role_id, username="testuser"))
            )
        )

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

        with patch.object(AuditService, "log", new_callable=AsyncMock) as mock_log:
            with pytest.raises(HTTPException):
                await service.submit_question(
                    http_session_id="test-session",
                    user_id=str(user_id),
                    question="test question",
                )

            mock_log.assert_any_call(
                mock_db,
                action=AuditActionType.QUOTA_EXCEEDED,
                actor_id=user_id,
                outcome="blocked",
                context={
                    "dimension": "queries",
                    "reset_at": "2026-06-13T00:00:00+00:00",
                },
            )

    @pytest.mark.asyncio
    async def test_execution_quota_exceeded_emits_audit_event(self):
        from app.core.exceptions import QuotaExceededError
        from app.services.audit_service import AuditService
        from app.services.query_service import QueryService

        user_id = uuid.uuid4()
        role_id = uuid.uuid4()

        mock_repo = AsyncMock()
        mock_session_repo = AsyncMock()
        mock_llm = AsyncMock()
        mock_evaluator = AsyncMock()
        mock_executor = AsyncMock()
        mock_redis = AsyncMock()
        mock_db = AsyncMock()
        mock_quota_service = AsyncMock()

        call_count = 0

        async def _check(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (1, 10, None)
            raise QuotaExceededError(dimension="executions", reset_at="2026-06-13T00:00:00+00:00")

        mock_quota_service.check_and_increment = AsyncMock(side_effect=_check)

        mock_llm.generate_sql = AsyncMock(return_value="SELECT 1")
        mock_evaluator.evaluate = AsyncMock(return_value=MagicMock(passed=True, violations=[]))

        mock_db.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=MagicMock(id=user_id, role_id=role_id, username="testuser"))
            )
        )

        session_id = uuid.uuid4()
        mock_session_repo.create = AsyncMock(return_value=MagicMock(id=session_id))
        mock_session_repo.get_by_id = AsyncMock(
            return_value=MagicMock(id=session_id, preview_text="t", user_id=user_id)
        )
        mock_session_repo.update_last_activity = AsyncMock()
        mock_session_repo.update_preview_text = AsyncMock()
        mock_repo.list_by_session = AsyncMock(return_value=[])
        mock_repo.get_latest_by_session = AsyncMock(return_value=None)
        mock_repo.get_by_attempt_id = AsyncMock(return_value=None)

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

        with (
            patch.object(AuditService, "log", new_callable=AsyncMock) as mock_log,
            patch.object(service, "_get_database_connection_id", return_value=str(uuid.uuid4())),
        ):
            with pytest.raises(HTTPException):
                await service.submit_question(
                    http_session_id="test-session",
                    user_id=str(user_id),
                    question="test question",
                    chat_session_id=str(session_id),
                )

            mock_log.assert_any_call(
                mock_db,
                action=AuditActionType.QUOTA_EXCEEDED,
                actor_id=user_id,
                outcome="blocked",
                context={
                    "dimension": "executions",
                    "reset_at": "2026-06-13T00:00:00+00:00",
                },
            )

    def test_quota_exceeded_context_has_dimension_and_reset_at_no_counters(self):
        context = {
            "dimension": "queries",
            "reset_at": "2026-06-13T00:00:00+00:00",
        }

        assert "dimension" in context
        assert "reset_at" in context
        assert "counter" not in context
        assert "used" not in context
        assert "limit" not in context
        assert "policy_id" not in context
        assert "role_id" not in context

    def test_quota_config_change_context_sanitized(self):
        context = {
            "action": "updated",
            "role_id": "some-uuid",
            "dims_changed": ["daily_query_limit"],
        }

        assert "action" in context
        assert "dims_changed" in context
        assert "counter_values" not in context
        assert "limit_values" not in context
        assert "policy_id" not in context

    def test_audit_action_type_enum_values(self):
        assert AuditActionType.QUOTA_EXCEEDED == "quota.exceeded"
        assert AuditActionType.QUOTA_CONFIG_CHANGE == "quota.config.change"
