"""T-151 regression test — reject/regenerate must validate attempt_id exists.

Currently if ``attempt_id`` does not exist in Redis, ``get_attempt`` raises
``AttemptNotFound``. Both ``reject_query`` and ``regenerate_query`` must
propagate this so the router returns HTTP 400.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import AttemptNotFound
from app.services.query_service import QueryService


@pytest.fixture
def service_with_mocked_deps():
    redis = AsyncMock()
    redis.get.return_value = None  # simulates missing attempt
    return QueryService(
        accepted_query_repository=MagicMock(),
        redis=redis,
        llm=AsyncMock(),
        evaluator=AsyncMock(),
        source_db_executor=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_reject_nonexistent_attempt_raises_attempt_not_found(service_with_mocked_deps):
    """Reject with a bogus attempt_id must raise AttemptNotFound."""
    with pytest.raises(AttemptNotFound):
        await service_with_mocked_deps.reject_query(
            attempt_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            session_id="sess-1",
        )


@pytest.mark.asyncio
async def test_regenerate_nonexistent_attempt_raises_attempt_not_found(service_with_mocked_deps):
    """Regenerate with a bogus attempt_id must raise AttemptNotFound."""
    with pytest.raises(AttemptNotFound):
        await service_with_mocked_deps.regenerate_query(
            attempt_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            session_id="sess-1",
        )
