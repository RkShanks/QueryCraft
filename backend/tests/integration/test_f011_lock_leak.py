"""F-011 — Processing lock leak in submit_question.

Reproduction tests for four paths where the lock is acquired but never released:
(a) LLM failure → HTTPException 502
(b) Evaluator rejection → EvaluatorRejection
(c) Executor timeout → HTTPException 504
(d) Success without follow-up → QueryResult, lock only released by accept/reject/regenerate

All tests are EXPECTED TO FAIL on current main (RED).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.query_service import QueryService

PROCESSING_KEY = "processing_lock:{session_id}"


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_evaluator():
    evaluator = AsyncMock()
    evaluator.evaluate.return_value = MagicMock(passed=True, violations=[])
    return evaluator


@pytest.fixture
def mock_executor():
    executor = AsyncMock()
    executor.execute.return_value = (
        [{"name": "id", "type": "integer"}],
        [[1]],
    )
    return executor


@pytest.fixture
def service(mock_repo, redis_client, mock_evaluator, mock_executor):
    return QueryService(
        accepted_query_repository=mock_repo,
        redis=redis_client,
        llm=AsyncMock(),
        evaluator=mock_evaluator,
        source_db_executor=mock_executor,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_f011a_lock_released_on_llm_failure(service, redis_client):
    """F-011a: lock must NOT outlive an LLM failure."""
    service._llm.generate_sql.side_effect = Exception("boom")

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_question(session_id="s1", user_id="u1", question="q")
    assert exc_info.value.status_code == 502

    assert await redis_client.exists(PROCESSING_KEY.format(session_id="s1")) == 0, \
        "F-011a: lock leaked after LLM failure"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_f011b_lock_released_on_evaluator_rejection(service, redis_client):
    """F-011b: lock must NOT outlive an evaluator rejection."""
    service._llm.generate_sql.return_value = "DELETE FROM users;"

    violation = MagicMock()
    violation.rule_name = "read_only"
    violation.message_key = "evaluator.violation.dataModifying"
    service._evaluator.evaluate.return_value = MagicMock(
        passed=False,
        violations=[violation],
    )

    result = await service.submit_question(session_id="s2", user_id="u1", question="q")
    assert result.message_key == "query.evaluator.rejected"

    assert await redis_client.exists(PROCESSING_KEY.format(session_id="s2")) == 0, \
        "F-011b: lock leaked after evaluator rejection"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_f011c_lock_released_on_executor_timeout(service, redis_client):
    """F-011c: lock must NOT outlive an executor timeout."""
    service._llm.generate_sql.return_value = "SELECT pg_sleep(60);"
    service._executor.execute.side_effect = TimeoutError()

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_question(session_id="s3", user_id="u1", question="q")
    assert exc_info.value.status_code == 504

    assert await redis_client.exists(PROCESSING_KEY.format(session_id="s3")) == 0, \
        "F-011c: lock leaked after executor timeout"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_f011d_lock_released_on_success_without_followup(service, redis_client):
    """F-011d: lock must NOT outlive a successful submit if user idles.

    Submit a query that succeeds. Without calling accept/reject/regenerate,
    the lock should already be released so a fresh submit on the same
    session is not 409'd.
    """
    service._llm.generate_sql.return_value = "SELECT 1 AS id"
    service._executor.execute.return_value = (
        [{"name": "id", "type": "integer"}],
        [[1]],
    )

    result = await service.submit_question(session_id="s4", user_id="u1", question="q")
    assert result.kind == "result"

    # Without accept/reject/regenerate, the lock should already be gone.
    assert await redis_client.exists(PROCESSING_KEY.format(session_id="s4")) == 0, \
        "F-011d: lock leaked after successful submit without follow-up"

    # A fresh submit on the same session must not be 409'd.
    result2 = await service.submit_question(session_id="s4", user_id="u1", question="q2")
    assert result2.kind == "result", "F-011d: second submit 409'd because lock leaked"
