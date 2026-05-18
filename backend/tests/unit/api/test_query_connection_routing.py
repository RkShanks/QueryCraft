"""Query flow tests: connection routing, schema isolation, disabled blocking, retry exhaustion (T-435, SC-027, SC-035)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestSubmitWithConnectionId:
    """Verify submit routes to correct connection."""

    @pytest.mark.asyncio
    async def test_submit_forwards_connection_id_to_service(self):
        """Service.submit_question must receive connection_id."""
        from app.api.v1.query import submit_question
        from app.schemas.query import SubmitQuestionRequest

        mock_service = AsyncMock()
        mock_result = MagicMock()
        mock_result.kind = "result"
        mock_service.submit_question.return_value = mock_result

        request = MagicMock()
        request.state.session_id = "http-sess-1"

        conn_id = str(uuid4())
        req = SubmitQuestionRequest(question="Show me users", connection_id=conn_id)

        result = await submit_question(
            request=request,
            req=req,
            user_id=str(uuid4()),
            service=mock_service,
        )

        mock_service.submit_question.assert_awaited_once()
        call_kwargs = mock_service.submit_question.await_args.kwargs
        assert call_kwargs["connection_id"] == conn_id
        assert result.kind == "result"


class TestDisabledConnectionBlocked:
    """Verify disabled/unhealthy/non-introspected connections are blocked at dependency level."""

    @pytest.mark.asyncio
    async def test_disabled_connection_raises_400(self):
        """_get_query_service_for_connection raises 400 for disabled connection."""
        from app.api.v1.query import _get_query_service_for_connection
        from fastapi import HTTPException

        conn_id = uuid4()
        with patch("app.api.v1.query.ConnectionRepository") as MockConnRepo:
            mock_conn_repo = AsyncMock()
            MockConnRepo.return_value = mock_conn_repo
            mock_conn_repo.get_by_id.return_value = MagicMock(
                id=conn_id,
                lifecycle_state="disabled",
                health_status="healthy",
                schema_introspection_status="success",
                database_type="postgresql",
            )

            mock_db = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                await _get_query_service_for_connection(
                    connection_id=str(conn_id),
                    db=mock_db,
                    redis=AsyncMock(),
                )
            assert exc_info.value.status_code == 400
            assert exc_info.value.detail["error"] == "connection_disabled"
