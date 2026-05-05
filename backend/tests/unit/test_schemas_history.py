"""Tests for history Pydantic schema validation (T-040).

Validates HistoryListResponse contains items list and nullable cursor;
AcceptedQueryDetail includes all required fields per openapi.yaml.
"""

import pytest
from pydantic import ValidationError

from app.schemas.history import AcceptedQueryDetail, HistoryListResponse


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
