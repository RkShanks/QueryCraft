"""F-011 — Processing lock leak in submit_question.

Reproduction tests for four paths where the lock is acquired but never released:
(a) LLM failure → HTTPException 502
(b) Evaluator rejection → EvaluatorRejection
(c) Executor timeout → HTTPException 504
(d) Success without follow-up → QueryResult, lock released immediately after submit
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.services.query_service import QueryService

PROCESSING_KEY = "processing_lock:{session_id}"
USER_ID = "00000000-0000-0000-0000-000000000001"


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
def service(mock_repo, redis_client, mock_evaluator, mock_executor, monkeypatch):
    monkeypatch.setattr(
        "app.services.query_service.DetectionConfigRepository.get",
        AsyncMock(return_value=SimpleNamespace(block_confidence=0.8, flag_confidence=0.5)),
    )
    monkeypatch.setattr(
        "app.services.query_service.HostileInputDetector.detect",
        AsyncMock(return_value=SimpleNamespace(outcome="allowed", results=[])),
    )
    monkeypatch.setattr("app.services.query_service.AuditService.log", AsyncMock(return_value=None))

    session_repo = AsyncMock()
    session_repo.create = AsyncMock(return_value=SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000010")))
    session_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            id=UUID("00000000-0000-0000-0000-000000000010"),
            preview_text="",
        )
    )
    session_repo.update_last_activity = AsyncMock(return_value=True)
    session_repo.update_preview_text = AsyncMock(return_value=True)
    mock_repo.get_latest_by_session = AsyncMock(return_value=None)
    mock_repo.list_by_session = AsyncMock(return_value=[])
    mock_repo.get_by_attempt_id = AsyncMock(return_value=None)
    mock_repo.create = AsyncMock(return_value=SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000030")))
    db_session = AsyncMock()
    db_session.execute = AsyncMock(
        return_value=SimpleNamespace(
            scalar_one_or_none=lambda: SimpleNamespace(username="test-user", role_id=None),
        )
    )
    db_session.flush = AsyncMock()

    service = QueryService(
        accepted_query_repository=mock_repo,
        session_repository=session_repo,
        db_session=db_session,
        redis=redis_client,
        llm=AsyncMock(),
        evaluator=mock_evaluator,
        source_db_executor=mock_executor,
    )
    service._get_llm_context_cap = AsyncMock(return_value=0)
    service._resolve_role_policy = AsyncMock(return_value=None)
    service._get_database_connection_id = AsyncMock(return_value="00000000-0000-0000-0000-000000000020")
    return service


@pytest.mark.integration
@pytest.mark.asyncio
async def test_f011a_lock_released_on_llm_failure(service, redis_client):
    """F-011a: lock must NOT outlive an LLM failure."""
    service._llm.generate_sql.side_effect = Exception("boom")

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_question(http_session_id="s1", user_id=USER_ID, question="q")
    assert exc_info.value.status_code == 502

    assert await redis_client.exists(PROCESSING_KEY.format(session_id="s1")) == 0, (
        "F-011a: lock leaked after LLM failure"
    )


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

    result = await service.submit_question(http_session_id="s2", user_id=USER_ID, question="q")
    assert result.message_key == "query.evaluator.rejected"

    assert await redis_client.exists(PROCESSING_KEY.format(session_id="s2")) == 0, (
        "F-011b: lock leaked after evaluator rejection"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_f011c_lock_released_on_executor_timeout(service, redis_client):
    """F-011c: lock must NOT outlive an executor timeout."""
    service._llm.generate_sql.return_value = "SELECT pg_sleep(60);"
    service._executor.execute.side_effect = TimeoutError()

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_question(http_session_id="s3", user_id=USER_ID, question="q")
    assert exc_info.value.status_code == 504

    assert await redis_client.exists(PROCESSING_KEY.format(session_id="s3")) == 0, (
        "F-011c: lock leaked after executor timeout"
    )


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

    result = await service.submit_question(http_session_id="s4", user_id=USER_ID, question="q")
    assert result.kind == "result"

    # Without accept/reject/regenerate, the lock should already be gone.
    assert await redis_client.exists(PROCESSING_KEY.format(session_id="s4")) == 0, (
        "F-011d: lock leaked after successful submit without follow-up"
    )

    # A fresh submit on the same session must not be 409'd.
    result2 = await service.submit_question(http_session_id="s4", user_id=USER_ID, question="q2")
    assert result2.kind == "result", "F-011d: second submit 409'd because lock leaked"
