"""Unit tests for HistoryService (T-053).

Tests list_history returns reverse-chronological entries with cursor,
get_detail returns full entry or 404; uses mocked repository.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.history_service import HistoryService


class TestHistoryService:
    """HistoryService unit tests with mocked repository."""

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.list_by_user = AsyncMock(return_value=([], None))
        repo.get_by_id = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def service(self, mock_repo):
        return HistoryService(mock_repo)

    @pytest.mark.asyncio
    async def test_list_history_returns_items(self, service, mock_repo):
        mock_repo.list_by_user.return_value = (
            [MagicMock(id="q-1", question_text="Q1", generated_sql="S1", accepted_at="2026-05-04T12:00:00Z")],
            None,
        )
        resp = await service.list_history("u-1", cursor=None, limit=10)
        assert len(resp.items) == 1
        assert resp.items[0].id == "q-1"
        assert resp.next_cursor is None

    @pytest.mark.asyncio
    async def test_get_detail_returns_entry(self, service, mock_repo):
        mock_repo.get_by_id.return_value = MagicMock(
            id="q-1",
            question_text="Q1",
            generated_sql="S1",
            llm_provider="ollama",
            accepted_at="2026-05-04T12:00:00Z",
            database_connection_id="db-1",
        )
        detail = await service.get_detail("q-1", "u-1")
        assert detail.id == "q-1"

    @pytest.mark.asyncio
    async def test_get_detail_not_found_raises_404(self, service, mock_repo):
        mock_repo.get_by_id.return_value = None
        with pytest.raises(Exception) as exc_info:
            await service.get_detail("q-1", "u-1")
        assert exc_info.value.status_code == 404
