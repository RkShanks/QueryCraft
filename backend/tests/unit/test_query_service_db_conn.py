"""Unit tests for QueryService missing DB connection handling.

Validates that _get_database_connection_id raises a controlled HTTPException
instead of returning nil UUID.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.query_service import QueryService


@pytest.mark.asyncio
async def test_get_database_connection_id_missing_raises_500():
    """Missing database_connections row raises 500 with clear message_key."""
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


@pytest.mark.asyncio
async def test_get_database_connection_id_returns_id_when_present():
    """Row present returns the id string."""
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
    )
    result = await service._get_database_connection_id()
    assert result == "aaaaaaaa-0000-0000-0000-000000000001"
