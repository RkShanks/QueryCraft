"""Detection administration remains read-only when singleton state is corrupt."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import MultipleResultsFound

from app.api.v1 import admin_detection


def _session_for_state(state: str):
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    query_result = MagicMock()
    if state == "missing":
        query_result.scalar_one_or_none.return_value = None
    elif state == "duplicate":
        query_result.scalar_one_or_none.side_effect = MultipleResultsFound()
    else:
        query_result.scalar_one_or_none.return_value = MagicMock(
            block_confidence=float("nan"),
            flag_confidence=0.5,
            updated_at=datetime.now(UTC),
        )
    session.execute = AsyncMock(return_value=query_result)
    return session


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["missing", "duplicate", "invalid"])
@pytest.mark.parametrize("method", ["get", "put"])
async def test_corrupt_admin_detection_state_returns_sanitized_503_without_repair(
    state: str,
    method: str,
) -> None:
    session = _session_for_state(state)

    with pytest.raises(HTTPException) as unavailable:
        if method == "get":
            await admin_detection.get_detection_config(_session={}, db=session)
        else:
            from app.schemas.detection import DetectionThresholdUpdate

            await admin_detection.update_detection_config(
                DetectionThresholdUpdate(block_confidence=0.9, flag_confidence=0.4),
                _session={},
                db=session,
            )

    assert unavailable.value.status_code == 503
    assert unavailable.value.detail == {
        "error": "service_unavailable",
        "message_key": "error.service_unavailable",
    }
    session.add.assert_not_called()
    session.flush.assert_not_awaited()
