"""T-151 regression test — reject/regenerate must validate attempt_id exists.

G-001+G-004: active_attempt check happens before get_attempt.
A non-existent/mismatched attempt_id now raises HTTPException(422).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.query_service import QueryService


@pytest.fixture
def service_with_mocked_deps():
    redis = AsyncMock()
    redis.get.return_value = None  # simulates no active attempt
    return QueryService(
        accepted_query_repository=MagicMock(),
        redis=redis,
        llm=AsyncMock(),
        evaluator=AsyncMock(),
        source_db_executor=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_reject_nonexistent_attempt_returns_422(service_with_mocked_deps):
    """Reject with a bogus attempt_id returns 422 (active_attempt mismatch)."""
    with pytest.raises(Exception) as exc_info:
        await service_with_mocked_deps.reject_query(
            attempt_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            session_id="sess-1",
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_regenerate_nonexistent_attempt_returns_422(service_with_mocked_deps):
    """Regenerate with a bogus attempt_id returns 422 (active_attempt mismatch)."""
    with pytest.raises(Exception) as exc_info:
        await service_with_mocked_deps.regenerate_query(
            attempt_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            session_id="sess-1",
        )
    assert exc_info.value.status_code == 422
