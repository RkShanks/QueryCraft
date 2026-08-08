"""IS-GAP-003 session deletion/query cancellation regressions."""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import text

from app.core.dependencies import get_redis
from app.core.session_cancellation import (
    QueryOperation,
    TrackedAttempt,
    cleanup_cancelled_session_state,
    mark_session_cancelling,
    register_query_operation,
    track_session_attempt,
)
from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.repositories.session_repository import SessionRepository
from app.source_db.adapters import ExecuteResult, PostgresAdapter

_PRIVATE_NOT_FOUND = {
    "error": "not_found",
    "message_key": "error.notFound",
}


async def _wait_for_value(redis_client, key: str) -> str:
    for _ in range(200):
        value = await redis_client.get(key)
        if value is not None:
            return value
        await asyncio.sleep(0.01)
    raise AssertionError(f"Redis state was not created for {key.split(':', maxsplit=1)[0]}")


async def _create_chat_session(authenticated_client) -> str:
    response = await authenticated_client.post("/api/v1/sessions")
    assert response.status_code == 201
    return response.json()["id"]


def _start_submit(authenticated_client, query_submit_payload, chat_session_id: str):
    return asyncio.create_task(
        authenticated_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload("Controlled cancellation", session_id=chat_session_id),
        )
    )


async def _assert_query_state_removed(redis_client, chat_session_id: str, operation: str) -> None:
    _user_id, http_session_id, attempt_id, _lock_owner, _token = operation.split("|")
    assert await redis_client.get(f"session_operation:{chat_session_id}") is None
    assert await redis_client.exists(f"session_attempts:{chat_session_id}") == 0
    assert await redis_client.get(f"attempt:{attempt_id}") is None
    assert await redis_client.get(f"active_attempt:{http_session_id}") is None
    assert await redis_client.get(f"processing_lock:{http_session_id}") is None


class _ControllableProvider:
    def __init__(self, *, finish_after_cancel: bool = False) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.finish_after_cancel = finish_after_cancel

    async def generate_sql(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        self.entered.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            if not self.finish_after_cancel:
                raise
            await self.release.wait()
        return "SELECT 1 AS id"


class _ControllableEvaluator:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def evaluate(self, *_args, **_kwargs):
        self.entered.set()
        await self.release.wait()
        return SimpleNamespace(passed=True, violations=[])


class _ControllableSource:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def execute(self, *_args, **_kwargs) -> ExecuteResult:
        self.entered.set()
        await self.release.wait()
        return ExecuteResult(columns=["id"], rows=[(1,)])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_is_gap_003_delete_during_provider_invalidates_late_submit(
    authenticated_client,
    query_submit_payload,
    redis_client,
):
    """Same-process DELETE cancels provider work and returns the private 404."""
    chat_session_id = await _create_chat_session(authenticated_client)
    provider = _ControllableProvider()

    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
        patch(
            "app.source_db.adapters.PostgresAdapter.execute",
            new=AsyncMock(return_value=ExecuteResult(columns=["id"], rows=[(1,)])),
        ),
    ):
        submit_task = _start_submit(authenticated_client, query_submit_payload, chat_session_id)
        await asyncio.wait_for(provider.entered.wait(), timeout=2)
        operation = await _wait_for_value(redis_client, f"session_operation:{chat_session_id}")
        delete_task = asyncio.create_task(authenticated_client.delete(f"/api/v1/sessions/{chat_session_id}"))

        try:
            delete_response = await asyncio.wait_for(asyncio.shield(delete_task), timeout=2)
            submit_response = await asyncio.wait_for(asyncio.shield(submit_task), timeout=2)
        finally:
            provider.release.set()
            await asyncio.gather(submit_task, delete_task, return_exceptions=True)

    assert delete_response.status_code == 204
    assert submit_response.status_code == 404
    assert submit_response.json() == _PRIVATE_NOT_FOUND
    await _assert_query_state_removed(redis_client, chat_session_id, operation)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_during_evaluator_cancels_before_source_execution(
    authenticated_client,
    query_submit_payload,
):
    chat_session_id = await _create_chat_session(authenticated_client)
    evaluator = _ControllableEvaluator()
    source = AsyncMock(return_value=ExecuteResult(columns=["id"], rows=[(1,)]))
    provider = AsyncMock(generate_sql=AsyncMock(return_value="SELECT 1 AS id"))

    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
        patch("app.evaluator.pipeline.Evaluator.evaluate", new=evaluator.evaluate),
        patch("app.source_db.adapters.PostgresAdapter.execute", new=source),
    ):
        submit_task = _start_submit(authenticated_client, query_submit_payload, chat_session_id)
        await asyncio.wait_for(evaluator.entered.wait(), timeout=2)
        delete_response = await authenticated_client.delete(f"/api/v1/sessions/{chat_session_id}")
        submit_response = await submit_task

    assert delete_response.status_code == 204
    assert submit_response.status_code == 404
    assert submit_response.json() == _PRIVATE_NOT_FOUND
    source.assert_not_awaited()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_during_source_execution_cancels_same_process_adapter(
    authenticated_client,
    query_submit_payload,
):
    chat_session_id = await _create_chat_session(authenticated_client)
    source = _ControllableSource()
    provider = AsyncMock(generate_sql=AsyncMock(return_value="SELECT 1 AS id"))

    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
        patch("app.source_db.adapters.PostgresAdapter.execute", new=source.execute),
    ):
        submit_task = _start_submit(authenticated_client, query_submit_payload, chat_session_id)
        await asyncio.wait_for(source.entered.wait(), timeout=2)
        delete_response = await authenticated_client.delete(f"/api/v1/sessions/{chat_session_id}")
        submit_response = await submit_task

    assert delete_response.status_code == 204
    assert submit_response.status_code == 404
    assert submit_response.json() == _PRIVATE_NOT_FOUND


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_interrupts_real_postgres_source_execution(
    authenticated_client,
    query_submit_payload,
    test_env_vars,
):
    """The real asyncpg adapter is interrupted while its query is active."""
    chat_session_id = await _create_chat_session(authenticated_client)
    provider = AsyncMock(generate_sql=AsyncMock(return_value="SELECT customer_id FROM customer"))
    observer = await asyncpg.connect(
        host=test_env_vars["SOURCE_DB_HOST"],
        port=int(test_env_vars["SOURCE_DB_PORT"]),
        database=test_env_vars["SOURCE_DB_NAME"],
        user="source_readonly",
        password="source_dev",
    )
    await observer.execute("BEGIN")
    await observer.execute("LOCK TABLE customer IN ACCESS EXCLUSIVE MODE")
    source_entered = asyncio.Event()
    original_execute = PostgresAdapter.execute

    async def observed_execute(adapter, sql, params=()):
        source_entered.set()
        return await original_execute(adapter, sql, params)

    async def execution_count() -> int:
        await observer.execute("SELECT pg_stat_clear_snapshot()")
        return int(
            await observer.fetchval(
                """
                SELECT count(*)
                FROM pg_stat_activity
                WHERE state = 'active'
                  AND query LIKE 'SELECT customer_id FROM customer%'
                  AND wait_event_type = 'Lock'
                """
            )
        )

    try:
        with (
            patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
            patch.object(PostgresAdapter, "execute", new=observed_execute),
        ):
            submit_task = _start_submit(authenticated_client, query_submit_payload, chat_session_id)
            await asyncio.wait_for(source_entered.wait(), timeout=5)
            for _ in range(200):
                if await execution_count() == 1:
                    break
                if submit_task.done():
                    early_response = submit_task.result()
                    raise AssertionError(
                        f"Submit ended before source execution: {early_response.status_code} {early_response.json()}"
                    )
                await asyncio.sleep(0.01)
            else:
                raise AssertionError("The real PostgreSQL source query did not become active")

            delete_response = await authenticated_client.delete(f"/api/v1/sessions/{chat_session_id}")
            submit_response = await submit_task

        assert delete_response.status_code == 204
        assert submit_response.status_code == 404
        for _ in range(200):
            if await execution_count() == 0:
                break
            await asyncio.sleep(0.01)
        assert await execution_count() == 0
    finally:
        await observer.execute("ROLLBACK")
        await observer.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_second_worker_marker_suppresses_late_provider_completion(
    authenticated_client,
    query_submit_payload,
    redis_client,
):
    chat_session_id = await _create_chat_session(authenticated_client)
    provider = _ControllableProvider(finish_after_cancel=True)

    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
        patch("app.api.v1.sessions.cancel_local_session_work", return_value=0),
        patch(
            "app.source_db.adapters.PostgresAdapter.execute",
            new=AsyncMock(return_value=ExecuteResult(columns=["id"], rows=[(1,)])),
        ),
    ):
        submit_task = _start_submit(authenticated_client, query_submit_payload, chat_session_id)
        await asyncio.wait_for(provider.entered.wait(), timeout=2)
        delete_task = asyncio.create_task(authenticated_client.delete(f"/api/v1/sessions/{chat_session_id}"))
        await _wait_for_value(redis_client, f"session_cancelled:{chat_session_id}")
        provider.release.set()
        delete_response, submit_response = await asyncio.gather(delete_task, submit_task)

    assert delete_response.status_code == 204
    assert submit_response.status_code == 404
    assert submit_response.json() == _PRIVATE_NOT_FOUND


@pytest.mark.integration
@pytest.mark.asyncio
async def test_second_worker_marker_suppresses_late_adapter_completion(
    authenticated_client,
    query_submit_payload,
    redis_client,
):
    chat_session_id = await _create_chat_session(authenticated_client)
    source = _ControllableSource()
    provider = AsyncMock(generate_sql=AsyncMock(return_value="SELECT 1 AS id"))

    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
        patch("app.api.v1.sessions.cancel_local_session_work", return_value=0),
        patch("app.source_db.adapters.PostgresAdapter.execute", new=source.execute),
    ):
        submit_task = _start_submit(authenticated_client, query_submit_payload, chat_session_id)
        await asyncio.wait_for(source.entered.wait(), timeout=2)
        delete_task = asyncio.create_task(authenticated_client.delete(f"/api/v1/sessions/{chat_session_id}"))
        await _wait_for_value(redis_client, f"session_cancelled:{chat_session_id}")
        source.release.set()
        delete_response, submit_response = await asyncio.gather(delete_task, submit_task)

    assert delete_response.status_code == 204
    assert submit_response.status_code == 404
    assert submit_response.json() == _PRIVATE_NOT_FOUND


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_immediately_before_persistence_rolls_back_success_state(
    authenticated_client,
    query_submit_payload,
    redis_client,
    async_engine_fixture,
):
    chat_session_id = await _create_chat_session(authenticated_client)
    persistence_entered = asyncio.Event()
    release_persistence = asyncio.Event()
    original_create = AcceptedQueryRepository.create

    async def pause_before_create(repository, **kwargs):
        persistence_entered.set()
        await release_persistence.wait()
        return await original_create(repository, **kwargs)

    async with async_engine_fixture.connect() as connection:
        before_success_audits = int(
            await connection.scalar(
                text(
                    "SELECT count(*) FROM audit_log_entries WHERE action_type = 'query.execute' AND outcome = 'success'"
                )
            )
            or 0
        )

    provider = AsyncMock(generate_sql=AsyncMock(return_value="SELECT 1 AS id"))
    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
        patch(
            "app.source_db.adapters.PostgresAdapter.execute",
            new=AsyncMock(return_value=ExecuteResult(columns=["id"], rows=[(1,)])),
        ),
        patch.object(AcceptedQueryRepository, "create", new=pause_before_create),
    ):
        submit_task = _start_submit(authenticated_client, query_submit_payload, chat_session_id)
        await asyncio.wait_for(persistence_entered.wait(), timeout=2)
        delete_task = asyncio.create_task(authenticated_client.delete(f"/api/v1/sessions/{chat_session_id}"))
        await _wait_for_value(redis_client, f"session_cancelled:{chat_session_id}")
        release_persistence.set()
        delete_response, submit_response = await asyncio.gather(delete_task, submit_task)

    assert delete_response.status_code == 204
    assert submit_response.status_code == 404
    async with async_engine_fixture.connect() as connection:
        assert (
            await connection.scalar(
                text(
                    "SELECT count(*) FROM audit_log_entries WHERE action_type = 'query.execute' AND outcome = 'success'"
                )
            )
            == before_success_audits
        )
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM accepted_queries WHERE session_id = CAST(:session_id AS uuid)"),
                {"session_id": chat_session_id},
            )
            == 0
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_duplicate_delete_has_one_winner_and_private_loser(authenticated_client):
    chat_session_id = await _create_chat_session(authenticated_client)
    responses = await asyncio.gather(
        authenticated_client.delete(f"/api/v1/sessions/{chat_session_id}"),
        authenticated_client.delete(f"/api/v1/sessions/{chat_session_id}"),
    )
    assert sorted(response.status_code for response in responses) == [204, 404]
    assert next(response for response in responses if response.status_code == 404).json() == _PRIVATE_NOT_FOUND


@pytest.mark.integration
@pytest.mark.asyncio
async def test_missing_and_malformed_delete_preserve_private_contract(authenticated_client, redis_client):
    missing_id = str(uuid.uuid4())
    missing = await authenticated_client.delete(f"/api/v1/sessions/{missing_id}")
    malformed = await authenticated_client.delete("/api/v1/sessions/not-a-uuid")

    assert missing.status_code == 404
    assert missing.json() == _PRIVATE_NOT_FOUND
    assert await redis_client.get(f"session_cancelled:{missing_id}") is None
    assert malformed.status_code == 422
    assert malformed.json()["error"] == "validation"
    assert "not-a-uuid" not in malformed.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_wrong_user_delete_does_not_mark_or_remove_session(
    authenticated_client,
    redis_client,
    async_engine_fixture,
):
    other_user_id = str(uuid.uuid4())
    other_session_id = str(uuid.uuid4())
    username = f"delete-owner-{uuid.uuid4()}"
    async with async_engine_fixture.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO users (id, username, display_name, role)
                VALUES (CAST(:user_id AS uuid), :username, 'Delete owner', 'admin')
                """
            ),
            {"user_id": other_user_id, "username": username},
        )
        await connection.execute(
            text(
                """
                INSERT INTO sessions (id, user_id, preview_text)
                VALUES (CAST(:session_id AS uuid), CAST(:user_id AS uuid), 'Private session')
                """
            ),
            {"session_id": other_session_id, "user_id": other_user_id},
        )

    try:
        response = await authenticated_client.delete(f"/api/v1/sessions/{other_session_id}")
        assert response.status_code == 404
        assert response.json() == _PRIVATE_NOT_FOUND
        assert await redis_client.get(f"session_cancelled:{other_session_id}") is None
        async with async_engine_fixture.connect() as connection:
            assert (
                await connection.scalar(
                    text("SELECT count(*) FROM sessions WHERE id = CAST(:session_id AS uuid)"),
                    {"session_id": other_session_id},
                )
                == 1
            )
    finally:
        async with async_engine_fixture.begin() as connection:
            await connection.execute(
                text("DELETE FROM users WHERE id = CAST(:user_id AS uuid)"),
                {"user_id": other_user_id},
            )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_failure_fails_closed_before_database_delete(
    authenticated_client,
):
    chat_session_id = await _create_chat_session(authenticated_client)

    class FailingRedis:
        async def set(self, *_args, **_kwargs):
            raise RedisConnectionError("private dependency address")

    async def failing_redis():
        yield FailingRedis()

    app = authenticated_client._transport.app
    app.dependency_overrides[get_redis] = failing_redis
    try:
        response = await authenticated_client.delete(f"/api/v1/sessions/{chat_session_id}")
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert response.status_code == 503
    assert response.json() == {
        "error": "service_unavailable",
        "message_key": "error.service_unavailable",
    }
    assert "private dependency address" not in response.text
    assert (await authenticated_client.get(f"/api/v1/sessions/{chat_session_id}")).status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_delete_rollback_clears_owned_marker(
    authenticated_client,
    redis_client,
):
    chat_session_id = await _create_chat_session(authenticated_client)
    app = authenticated_client._transport.app
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch.object(SessionRepository, "delete", new=AsyncMock(side_effect=RuntimeError("private DB failure"))):
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies=authenticated_client.cookies,
            headers={"origin": "http://test"},
        ) as client:
            response = await client.delete(f"/api/v1/sessions/{chat_session_id}")

    assert response.status_code == 500
    assert "private DB failure" not in response.text
    assert await redis_client.get(f"session_cancelled:{chat_session_id}") is None
    assert (await authenticated_client.get(f"/api/v1/sessions/{chat_session_id}")).status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cancelled_cleanup_preserves_raced_lock_and_active_attempt_owners(redis_client):
    chat_session_id = str(uuid.uuid4())
    marker = await mark_session_cancelling(chat_session_id, "owner-user", redis_client)
    assert marker is not None
    operation = QueryOperation(
        session_id=chat_session_id,
        user_id="owner-user",
        http_session_id="browser-session",
        attempt_id="cancelled-attempt",
        lock_owner="cancelled-lock-owner",
        token="operation-token",
    )
    tracked_attempt = TrackedAttempt(
        session_id=chat_session_id,
        user_id="owner-user",
        http_session_id="browser-session",
        attempt_id="cancelled-attempt",
    )
    assert await register_query_operation(operation, redis_client)
    await track_session_attempt(tracked_attempt, redis_client)
    older_attempt = TrackedAttempt(
        session_id=chat_session_id,
        user_id="owner-user",
        http_session_id="older-browser-session",
        attempt_id="older-cancelled-attempt",
    )
    await track_session_attempt(older_attempt, redis_client)
    await redis_client.set("attempt:cancelled-attempt", "state")
    await redis_client.set("attempt:older-cancelled-attempt", "older-state")
    await redis_client.set("processing_lock:browser-session", "new-lock-owner")
    await redis_client.set("active_attempt:browser-session", "new-attempt")

    assert await cleanup_cancelled_session_state(marker, redis_client)
    assert await redis_client.get("processing_lock:browser-session") == "new-lock-owner"
    assert await redis_client.get("active_attempt:browser-session") == "new-attempt"
    assert await redis_client.get("attempt:cancelled-attempt") is None
    assert await redis_client.get("attempt:older-cancelled-attempt") is None
    assert await redis_client.get(f"session_operation:{chat_session_id}") is None
    assert await redis_client.exists(f"session_attempts:{chat_session_id}") == 0
