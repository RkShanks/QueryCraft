"""IS-GAP-004 real HTTP deadline, persistence, audit, and cancellation proof."""

import asyncio
from time import monotonic
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.source_db.adapters import ExecuteResult

_TIMEOUT_DETAIL = {"error": "timeout", "message_key": "error.timeout"}


class _ControllableSlowProvider:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.finished = asyncio.Event()
        self.task: asyncio.Task | None = None

    async def generate_sql(self, *_args, **_kwargs) -> str:
        self.task = asyncio.current_task()
        self.entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.finished.set()


async def _audit_count(db_session, *, outcome: str) -> int:
    count = await db_session.scalar(
        text(
            """
            SELECT count(*)
            FROM audit_log_entries
            WHERE action_type = 'query.execute'
              AND outcome = :outcome
              AND context ->> 'reason' = 'timeout'
            """
        ),
        {"outcome": outcome},
    )
    return int(count or 0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_short_configured_deadline_controls_real_http_and_cleans_all_state(
    authenticated_client,
    query_submit_payload,
    db_session,
    redis_client,
    monkeypatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "QUERY_TIMEOUT_SECONDS", 1)
    provider = _ControllableSlowProvider()
    accepted_before = int(await db_session.scalar(text("SELECT count(*) FROM accepted_queries")) or 0)
    timeout_audits_before = await _audit_count(db_session, outcome="failure")

    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
        patch(
            "app.source_db.adapters.PostgresAdapter.execute",
            new=AsyncMock(return_value=ExecuteResult(columns=["id"], rows=[(1,)])),
        ),
    ):
        started_at = monotonic()
        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload("Bounded request"),
        )
        duration_seconds = monotonic() - started_at

    assert response.status_code == 504
    assert response.json() == _TIMEOUT_DETAIL
    assert 0.8 <= duration_seconds < 2.5
    assert provider.finished.is_set()
    assert provider.task is not None and provider.task.done()
    assert int(await db_session.scalar(text("SELECT count(*) FROM accepted_queries")) or 0) == accepted_before
    assert await _audit_count(db_session, outcome="failure") == timeout_audits_before + 1
    assert await redis_client.keys("processing_lock:*") == []
    assert await redis_client.keys("active_attempt:*") == []
    assert await redis_client.keys("session_operation:*") == []
    attempts = await redis_client.keys("attempt:*")
    assert len(attempts) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_delete_immediately_before_deadline_keeps_cancellation_contract(
    authenticated_client,
    query_submit_payload,
    db_session,
    redis_client,
    monkeypatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "QUERY_TIMEOUT_SECONDS", 1)
    provider = _ControllableSlowProvider()
    timeout_audits_before = await _audit_count(db_session, outcome="failure")
    session_response = await authenticated_client.post("/api/v1/sessions")
    assert session_response.status_code == 201
    chat_session_id = session_response.json()["id"]

    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
        patch(
            "app.source_db.adapters.PostgresAdapter.execute",
            new=AsyncMock(return_value=ExecuteResult(columns=["id"], rows=[(1,)])),
        ),
    ):
        submit_task = asyncio.create_task(
            authenticated_client.post(
                "/api/v1/query/submit",
                json=query_submit_payload("Cancellation wins", session_id=chat_session_id),
            )
        )
        await asyncio.wait_for(provider.entered.wait(), timeout=2)
        await asyncio.sleep(0.85)
        delete_response = await authenticated_client.delete(f"/api/v1/sessions/{chat_session_id}")
        submit_response = await submit_task

    assert delete_response.status_code == 204
    assert submit_response.status_code == 404
    assert submit_response.json() == {"error": "not_found", "message_key": "error.notFound"}
    assert await _audit_count(db_session, outcome="failure") == timeout_audits_before
    assert await redis_client.keys("processing_lock:*") == []
    assert await redis_client.keys("active_attempt:*") == []
    assert await redis_client.keys("session_operation:*") == []
