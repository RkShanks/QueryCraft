"""Audit coverage for allowed query-history access."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.enums import AuditActionType
from app.services.history_service import HistoryService


@pytest.mark.asyncio
async def test_history_list_writes_sanitized_audit_event():
    repository = MagicMock()
    repository.list_by_user = AsyncMock(return_value=([], None))
    repository.count_by_user = AsyncMock(return_value=0)
    service = HistoryService(
        repository,
        db_session=AsyncMock(),
    )

    with patch(
        "app.services.history_service.AuditService.log",
        new_callable=AsyncMock,
    ) as audit_log:
        result = await service.list_history(
            user_id="550e8400-e29b-41d4-a716-446655440000",
            actor_identity="history-user",
        )

    assert result.items == []
    audit_log.assert_awaited_once()
    call = audit_log.await_args.kwargs
    assert call["action"] is AuditActionType.QUERY_HISTORY_VIEW
    assert call["outcome"] == "success"
    assert call["resource_type"] == "accepted_query_history"
    assert call["resource_id"] is None
    assert call["context"] == {"operation": "list"}
