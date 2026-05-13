"""Tests for history Pydantic schema validation (T-040).

Validates HistoryListResponse contains items list and nullable cursor;
AcceptedQueryDetail includes all required fields per openapi.yaml.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.schemas.history import AcceptedQueryDetail, HistoryListResponse
from app.services.history_service import HistoryService


class TestHistoryListResponse:
    """Validation for history list response."""

    def test_contains_items_list(self):
        resp = HistoryListResponse(items=[])
        assert resp.items == []

    def test_nullable_cursor(self):
        resp = HistoryListResponse(items=[], next_cursor=None)
        assert resp.next_cursor is None

    def test_with_cursor(self):
        resp = HistoryListResponse(items=[], next_cursor="abc123")
        assert resp.next_cursor == "abc123"


class TestAcceptedQueryDetail:
    """Required field checks for history detail."""

    def test_includes_all_required_fields(self):
        detail = AcceptedQueryDetail(
            id="550e8400-e29b-41d4-a716-446655440000",
            question_text="What are top sales?",
            generated_sql="SELECT 1",
            llm_provider="ollama",
            accepted_at="2026-05-04T12:00:00Z",
            database_connection_id="550e8400-e29b-41d4-a716-446655440001",
        )
        assert detail.id == "550e8400-e29b-41d4-a716-446655440000"
        assert detail.question_text == "What are top sales?"
        assert detail.generated_sql == "SELECT 1"
        assert detail.llm_provider == "ollama"
        assert detail.accepted_at == "2026-05-04T12:00:00Z"
        assert detail.database_connection_id == "550e8400-e29b-41d4-a716-446655440001"

    def test_rejects_missing_id(self):
        with pytest.raises(ValidationError) as exc_info:
            AcceptedQueryDetail(
                question_text="Q",
                generated_sql="S",
                llm_provider="ollama",
                accepted_at="2026-05-04T12:00:00Z",
                database_connection_id="550e8400-e29b-41d4-a716-446655440001",
            )
        assert "id" in str(exc_info.value)

    def test_optional_result_payload_fields(self):
        detail = AcceptedQueryDetail(
            id="550e8400-e29b-41d4-a716-446655440000",
            question_text="What are top sales?",
            generated_sql="SELECT 1",
            llm_provider="ollama",
            accepted_at="2026-05-04T12:00:00Z",
            database_connection_id="550e8400-e29b-41d4-a716-446655440001",
            result_columns=[{"name": "count", "type": "integer"}],
            result_rows=[[42]],
            result_row_count=1,
        )
        assert detail.result_columns == [{"name": "count", "type": "integer"}]
        assert detail.result_rows == [[42]]
        assert detail.result_row_count == 1

    def test_result_payload_defaults_to_none(self):
        detail = AcceptedQueryDetail(
            id="id",
            question_text="Q",
            generated_sql="S",
            llm_provider="ollama",
            accepted_at="2026-05-04T12:00:00Z",
            database_connection_id="db",
        )
        assert detail.result_columns is None
        assert detail.result_rows is None
        assert detail.result_row_count is None


@pytest.mark.asyncio
async def test_history_service_get_detail_returns_result_payload():
    """HistoryService.get_detail returns result_columns/result_rows/result_row_count."""
    mock_query = MagicMock()
    mock_query.id = "550e8400-e29b-41d4-a716-446655440000"
    mock_query.question_text = "Q"
    mock_query.generated_sql = "SELECT 1"
    mock_query.llm_provider = "ollama"
    mock_query.accepted_at = MagicMock()
    mock_query.accepted_at.isoformat.return_value = "2026-05-04T12:00:00Z"
    mock_query.database_connection_id = MagicMock()
    mock_query.database_connection_id.__str__ = MagicMock(return_value="conn-1")
    mock_query.result_columns = [{"name": "count", "type": "integer"}]
    mock_query.result_rows = [[42]]
    mock_query.result_row_count = 1

    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=mock_query)
    service = HistoryService(repo)

    detail = await service.get_detail(
        query_id="550e8400-e29b-41d4-a716-446655440000",
        user_id="550e8400-e29b-41d4-a716-446655440001",
    )
    assert detail.result_columns == [{"name": "count", "type": "integer"}]
    assert detail.result_rows == [[42]]
    assert detail.result_row_count == 1
