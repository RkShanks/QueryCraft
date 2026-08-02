"""Unit tests for explicit QueryService source scoping.

Validates that the service never discovers an arbitrary default connection.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.query_service import QueryService


@pytest.mark.asyncio
async def test_get_database_connection_id_missing_raises_500():
    """A service without explicit source context fails closed."""
    db_session = AsyncMock()
    db_session.execute = AsyncMock(return_value=MagicMock(fetchone=MagicMock(return_value=None)))
    service = QueryService(
        accepted_query_repository=MagicMock(),
        session_repository=MagicMock(),
        db_session=db_session,
        redis=MagicMock(),
        llm=MagicMock(),
        evaluator=MagicMock(),
        source_db_executor=MagicMock(),
    )
    with pytest.raises(HTTPException) as exc_info:
        await service._get_database_connection_id()
    assert exc_info.value.status_code == 500
    detail = exc_info.value.detail
    assert detail["error"] == "config_error"
    assert detail["message_key"] == "error.sourceDbNotConfigured"
    db_session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_database_connection_id_returns_explicit_scope_only():
    """The constructor-scoped source is returned without querying a default row."""
    db_session = AsyncMock()
    db_session.execute = AsyncMock(
        return_value=MagicMock(fetchone=MagicMock(return_value=("aaaaaaaa-0000-0000-0000-000000000001",)))
    )
    service = QueryService(
        accepted_query_repository=MagicMock(),
        session_repository=MagicMock(),
        db_session=db_session,
        redis=MagicMock(),
        llm=MagicMock(),
        evaluator=MagicMock(),
        source_db_executor=MagicMock(),
        connection_id="aaaaaaaa-0000-0000-0000-000000000001",
    )
    result = await service._get_database_connection_id()
    assert result == "aaaaaaaa-0000-0000-0000-000000000001"
    db_session.execute.assert_not_awaited()
