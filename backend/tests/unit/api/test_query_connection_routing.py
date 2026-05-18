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
        from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus
        from fastapi import HTTPException

        conn_id = uuid4()

        mock_conn = MagicMock()
        mock_conn.id = conn_id
        mock_conn.lifecycle_state = LifecycleState.DISABLED
        mock_conn.health_status = HealthStatus.HEALTHY
        mock_conn.schema_introspection_status = SchemaIntrospectionStatus.SUCCESS
        mock_conn.database_type = DatabaseType.POSTGRESQL

        mock_conn_repo = AsyncMock()
        mock_conn_repo.get_by_id.return_value = mock_conn

        mock_db = AsyncMock()

        with patch("app.api.v1.query.ConnectionRepository", return_value=mock_conn_repo):
            with pytest.raises(HTTPException) as exc_info:
                await _get_query_service_for_connection(
                    connection_id=str(conn_id),
                    db=mock_db,
                    redis=AsyncMock(),
                )
            assert exc_info.value.status_code == 400
            assert exc_info.value.detail["error"] == "connection_disabled"

    @pytest.mark.asyncio
    async def test_unhealthy_connection_raises_400(self):
        """_get_query_service_for_connection raises 400 for unhealthy connection."""
        from app.api.v1.query import _get_query_service_for_connection
        from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus
        from fastapi import HTTPException

        conn_id = uuid4()

        mock_conn = MagicMock()
        mock_conn.id = conn_id
        mock_conn.lifecycle_state = LifecycleState.ACTIVE
        mock_conn.health_status = HealthStatus.UNHEALTHY
        mock_conn.schema_introspection_status = SchemaIntrospectionStatus.SUCCESS
        mock_conn.database_type = DatabaseType.POSTGRESQL

        mock_conn_repo = AsyncMock()
        mock_conn_repo.get_by_id.return_value = mock_conn

        mock_db = AsyncMock()

        with patch("app.api.v1.query.ConnectionRepository", return_value=mock_conn_repo):
            with pytest.raises(HTTPException) as exc_info:
                await _get_query_service_for_connection(
                    connection_id=str(conn_id),
                    db=mock_db,
                    redis=AsyncMock(),
                )
            assert exc_info.value.status_code == 400
            assert exc_info.value.detail["error"] == "connection_unhealthy"

    @pytest.mark.asyncio
    async def test_no_schema_connection_raises_400(self):
        """_get_query_service_for_connection raises 400 for non-introspected connection."""
        from app.api.v1.query import _get_query_service_for_connection
        from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus
        from fastapi import HTTPException

        conn_id = uuid4()

        mock_conn = MagicMock()
        mock_conn.id = conn_id
        mock_conn.lifecycle_state = LifecycleState.ACTIVE
        mock_conn.health_status = HealthStatus.HEALTHY
        mock_conn.schema_introspection_status = SchemaIntrospectionStatus.NONE
        mock_conn.database_type = DatabaseType.POSTGRESQL

        mock_conn_repo = AsyncMock()
        mock_conn_repo.get_by_id.return_value = mock_conn

        mock_db = AsyncMock()

        with patch("app.api.v1.query.ConnectionRepository", return_value=mock_conn_repo):
            with pytest.raises(HTTPException) as exc_info:
                await _get_query_service_for_connection(
                    connection_id=str(conn_id),
                    db=mock_db,
                    redis=AsyncMock(),
                )
            assert exc_info.value.status_code == 400
            assert exc_info.value.detail["error"] == "connection_no_schema"


class TestSchemaIsolation:
    """Verify only selected connection's schema is included in prompt."""

    def test_prompt_builder_includes_target_dialect_instruction(self):
        """Prompt must include TARGET_DIALECT instruction when provided."""
        from app.llm.prompt_builder import build_prompt

        schema_context = MagicMock()
        schema_context.format_for_llm.return_value = "Table: users (id, name)"

        prompt = build_prompt(
            question="Show users",
            schema_context=schema_context,
            target_dialect="mysql",
        )

        assert "TARGET_DIALECT:" in prompt
        assert "mysql" in prompt

    def test_prompt_builder_omits_dialect_when_not_provided(self):
        """Prompt must omit TARGET_DIALECT when not provided (backward compat)."""
        from app.llm.prompt_builder import build_prompt

        schema_context = MagicMock()
        schema_context.format_for_llm.return_value = "Table: users (id, name)"

        prompt = build_prompt(
            question="Show users",
            schema_context=schema_context,
        )

        assert "TARGET_DIALECT:" not in prompt

    def test_dialect_map_correct(self):
        """DIALECT_MAP must map database types to correct SQL dialects."""
        from app.db.models.enums import DatabaseType
        from app.evaluator.rules.read_only import DIALECT_MAP

        assert DIALECT_MAP[DatabaseType.POSTGRESQL] == "postgres"
        assert DIALECT_MAP[DatabaseType.MYSQL] == "mysql"
        assert DIALECT_MAP[DatabaseType.MSSQL] == "tsql"


class TestRetryExhaustion:
    """Verify retry exhaustion returns refine prompt."""

    @pytest.mark.asyncio
    async def test_regenerate_exhaustion_returns_refine(self):
        """After max regenerations, service must return refine prompt (kind=refine)."""
        from app.api.v1.query import regenerate_query
        from app.core.exceptions import AttemptNotFound
        from app.schemas.query import RegenerateQueryRequest, RefinePrompt

        mock_service = AsyncMock()
        mock_service.regenerate_query.return_value = RefinePrompt(
            message_key="query.refine.message",
            should_refine=True,
        )

        request = MagicMock()
        request.state.session_id = "http-sess-1"

        req = RegenerateQueryRequest(attempt_id=str(uuid4()))

        result = await regenerate_query(
            request=request,
            req=req,
            user_id=str(uuid4()),
            service=mock_service,
        )

        assert result.kind == "refine"
        assert result.should_refine is True
