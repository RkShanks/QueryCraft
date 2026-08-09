"""IS-GAP-005/006 real HTTP retry quota and audit lifecycle proof."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import QuotaUnavailableError
from app.db.models.enums import AuditActionType
from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.services.audit_service import AuditService
from app.services.quota_service import QuotaService
from app.source_db.adapters import ExecuteResult


class _ProviderSpy:
    def __init__(self) -> None:
        self.calls = 0
        self._total_calls = 0

    async def generate_sql(self, *_args, **_kwargs) -> str:
        self.calls += 1
        self._total_calls += 1
        return f"SELECT {self._total_calls} AS id"


class _SourceSpy:
    def __init__(self) -> None:
        self.calls = 0
        self.error: BaseException | None = None

    async def execute(self, *_args, **_kwargs) -> ExecuteResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return ExecuteResult(columns=["id"], rows=[(self.calls,)])


async def _admin_identity(async_engine_fixture) -> tuple[str, str]:
    async with async_engine_fixture.connect() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    SELECT users.id, users.role_id
                    FROM users
                    WHERE users.username = 'admin'
                    """
                )
            )
        ).one()
    return str(row.id), str(row.role_id)


async def _set_quotas(authenticated_client, role_id: str, *, queries: int, executions: int) -> None:
    response = await authenticated_client.put(
        f"/api/v1/admin/quotas/{role_id}",
        json={
            "daily_query_limit": queries,
            "daily_execution_limit": executions,
        },
    )
    assert response.status_code == 200


def _quota_key(user_id: str, dimension: str) -> str:
    return f"quota:{user_id}:{dimension}:{datetime.now(UTC):%Y-%m-%d}"


async def _counter(redis_client, user_id: str, dimension: str) -> int:
    value = await redis_client.get(_quota_key(user_id, dimension))
    return int(value or 0)


async def _audit_watermark(async_engine_fixture) -> int:
    async with async_engine_fixture.connect() as connection:
        value = await connection.scalar(text("SELECT COALESCE(MAX(sequence_number), 0) FROM audit_log_entries"))
    return int(value or 0)


async def _audit_rows(async_engine_fixture, after_sequence: int) -> list[dict]:
    async with async_engine_fixture.connect() as connection:
        result = await connection.execute(
            text(
                """
                SELECT sequence_number, action_type, resource_type, resource_id,
                       outcome, context
                FROM audit_log_entries
                WHERE sequence_number > :after_sequence
                ORDER BY sequence_number
                """
            ),
            {"after_sequence": after_sequence},
        )
        return [dict(row) for row in result.mappings()]


async def _assert_chain_valid(async_engine_fixture) -> None:
    async with AsyncSession(async_engine_fixture) as session:
        verification = await AuditService.verify_chain(session)
    assert verification.verified is True
    assert verification.first_break_at is None


async def _submit_initial_attempt(
    authenticated_client,
    query_submit_payload,
    provider: _ProviderSpy,
    source: _SourceSpy,
) -> dict:
    response = await authenticated_client.post(
        "/api/v1/query/submit",
        json=query_submit_payload("Retry accounting proof"),
    )
    assert response.status_code == 200, response.text
    provider.calls = 0
    source.calls = 0
    return response.json()


def _assert_safe_audit_context(rows: list[dict]) -> None:
    serialized = json.dumps([row["context"] for row in rows], sort_keys=True)
    lowered = serialized.lower()
    for forbidden in ("retry accounting proof", "select 1", "select 2", "provider", "redis"):
        assert forbidden not in lowered


@pytest.mark.parametrize("endpoint", ["regenerate", "reject"])
async def test_successful_retry_uses_one_real_counter_and_one_external_call(
    endpoint: str,
    authenticated_client,
    query_submit_payload,
    async_engine_fixture,
    redis_client,
) -> None:
    user_id, role_id = await _admin_identity(async_engine_fixture)
    await _set_quotas(authenticated_client, role_id, queries=100, executions=100)
    provider = _ProviderSpy()
    source = _SourceSpy()

    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
        patch("app.source_db.adapters.PostgresAdapter.execute", new=source.execute),
    ):
        initial = await _submit_initial_attempt(authenticated_client, query_submit_payload, provider, source)
        before_queries = await _counter(redis_client, user_id, "queries")
        before_executions = await _counter(redis_client, user_id, "executions")
        watermark = await _audit_watermark(async_engine_fixture)
        response = await authenticated_client.post(
            f"/api/v1/query/{endpoint}",
            json={"attempt_id": initial["attempt_id"]},
        )

    assert response.status_code == 200, response.text
    assert provider.calls == 1
    assert source.calls == 1
    assert await _counter(redis_client, user_id, "queries") == before_queries + 1
    assert await _counter(redis_client, user_id, "executions") == before_executions + 1

    rows = await _audit_rows(async_engine_fixture, watermark)
    expected = [
        AuditActionType.QUERY_SUBMIT.value,
        AuditActionType.QUERY_VALIDATE_PASS.value,
        AuditActionType.QUERY_EXECUTE.value,
    ]
    if endpoint == "reject":
        expected.insert(0, AuditActionType.QUERY_REJECT.value)
    assert [row["action_type"] for row in rows] == expected
    retry_rows = rows[1:] if endpoint == "reject" else rows
    assert {row["resource_id"] for row in retry_rows} == {response.json()["attempt_id"]}
    assert all(row["resource_type"] == "query_attempt" for row in rows)
    assert all(row["outcome"] == "success" for row in rows)
    _assert_safe_audit_context(rows)
    await _assert_chain_valid(async_engine_fixture)


@pytest.mark.parametrize("endpoint", ["regenerate", "reject"])
@pytest.mark.parametrize("counter_value", [1, 2], ids=["at-limit", "over-limit"])
async def test_query_quota_denial_is_sanitized_and_calls_nothing(
    endpoint: str,
    counter_value: int,
    authenticated_client,
    query_submit_payload,
    async_engine_fixture,
    redis_client,
) -> None:
    user_id, role_id = await _admin_identity(async_engine_fixture)
    await _set_quotas(authenticated_client, role_id, queries=1, executions=100)
    provider = _ProviderSpy()
    source = _SourceSpy()

    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
        patch("app.source_db.adapters.PostgresAdapter.execute", new=source.execute),
    ):
        initial = await _submit_initial_attempt(authenticated_client, query_submit_payload, provider, source)
        await redis_client.set(_quota_key(user_id, "queries"), counter_value)
        watermark = await _audit_watermark(async_engine_fixture)
        response = await authenticated_client.post(
            f"/api/v1/query/{endpoint}",
            json={"attempt_id": initial["attempt_id"]},
        )

    assert response.status_code == 429
    assert response.json()["error"] == "quota_exceeded"
    assert response.json()["message_key"] == "error.quota_exceeded"
    assert provider.calls == 0
    assert source.calls == 0
    assert await _counter(redis_client, user_id, "queries") == counter_value

    rows = await _audit_rows(async_engine_fixture, watermark)
    expected = [AuditActionType.QUOTA_EXCEEDED.value]
    if endpoint == "reject":
        expected.insert(0, AuditActionType.QUERY_REJECT.value)
    assert [row["action_type"] for row in rows] == expected
    assert rows[-1]["outcome"] == "blocked"
    _assert_safe_audit_context(rows)
    await _assert_chain_valid(async_engine_fixture)


@pytest.mark.parametrize("endpoint", ["regenerate", "reject"])
async def test_execution_quota_denial_charges_provider_but_never_source(
    endpoint: str,
    authenticated_client,
    query_submit_payload,
    async_engine_fixture,
    redis_client,
) -> None:
    user_id, role_id = await _admin_identity(async_engine_fixture)
    await _set_quotas(authenticated_client, role_id, queries=100, executions=1)
    provider = _ProviderSpy()
    source = _SourceSpy()

    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
        patch("app.source_db.adapters.PostgresAdapter.execute", new=source.execute),
    ):
        initial = await _submit_initial_attempt(authenticated_client, query_submit_payload, provider, source)
        before_queries = await _counter(redis_client, user_id, "queries")
        watermark = await _audit_watermark(async_engine_fixture)
        response = await authenticated_client.post(
            f"/api/v1/query/{endpoint}",
            json={"attempt_id": initial["attempt_id"]},
        )

    assert response.status_code == 429
    assert response.json()["message_key"] == "error.quota_exceeded"
    assert provider.calls == 1
    assert source.calls == 0
    assert await _counter(redis_client, user_id, "queries") == before_queries + 1
    assert await _counter(redis_client, user_id, "executions") == 1

    rows = await _audit_rows(async_engine_fixture, watermark)
    expected = [
        AuditActionType.QUERY_SUBMIT.value,
        AuditActionType.QUERY_VALIDATE_PASS.value,
        AuditActionType.QUOTA_EXCEEDED.value,
    ]
    if endpoint == "reject":
        expected.insert(0, AuditActionType.QUERY_REJECT.value)
    assert [row["action_type"] for row in rows] == expected
    assert rows[-1]["outcome"] == "blocked"
    await _assert_chain_valid(async_engine_fixture)


@pytest.mark.parametrize("dimension", ["queries", "executions"])
async def test_retry_quota_unavailable_returns_sanitized_503_without_unmetered_work(
    dimension: str,
    authenticated_client,
    query_submit_payload,
    async_engine_fixture,
) -> None:
    _user_id, role_id = await _admin_identity(async_engine_fixture)
    await _set_quotas(authenticated_client, role_id, queries=100, executions=100)
    provider = _ProviderSpy()
    source = _SourceSpy()
    original_consume = QuotaService.check_and_increment

    async def fail_selected_dimension(service, user_id, user_role_id, requested_dimension):
        if requested_dimension == dimension:
            raise QuotaUnavailableError()
        return await original_consume(service, user_id, user_role_id, requested_dimension)

    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
        patch("app.source_db.adapters.PostgresAdapter.execute", new=source.execute),
    ):
        initial = await _submit_initial_attempt(authenticated_client, query_submit_payload, provider, source)
        with patch.object(QuotaService, "check_and_increment", new=fail_selected_dimension):
            response = await authenticated_client.post(
                "/api/v1/query/regenerate",
                json={"attempt_id": initial["attempt_id"]},
            )

    assert response.status_code == 503
    assert response.json() == {
        "error": "service_unavailable",
        "message_key": "error.service_unavailable",
    }
    assert provider.calls == (0 if dimension == "queries" else 1)
    assert source.calls == 0


async def test_failed_retry_rolls_back_history_but_preserves_truthful_audit_chain(
    authenticated_client,
    query_submit_payload,
    async_engine_fixture,
    redis_client,
) -> None:
    _user_id, role_id = await _admin_identity(async_engine_fixture)
    await _set_quotas(authenticated_client, role_id, queries=100, executions=100)
    provider = _ProviderSpy()
    source = _SourceSpy()

    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
        patch("app.source_db.adapters.PostgresAdapter.execute", new=source.execute),
    ):
        initial = await _submit_initial_attempt(authenticated_client, query_submit_payload, provider, source)
        async with async_engine_fixture.connect() as connection:
            before = (
                await connection.execute(
                    text(
                        """
                        SELECT attempt_id, generated_sql
                        FROM accepted_queries
                        WHERE id = CAST(:accepted_query_id AS uuid)
                        """
                    ),
                    {"accepted_query_id": initial["accepted_query_id"]},
                )
            ).one()
        watermark = await _audit_watermark(async_engine_fixture)
        source.error = RuntimeError("source credential secret")
        response = await authenticated_client.post(
            "/api/v1/query/regenerate",
            json={"attempt_id": initial["attempt_id"]},
        )

    assert response.status_code == 502
    assert response.json() == {
        "error": "source_db_execution_failed",
        "message_key": "error.sourceDbExecutionFailed",
    }
    assert provider.calls == 1
    assert source.calls == 1

    async with async_engine_fixture.connect() as connection:
        after = (
            await connection.execute(
                text(
                    """
                    SELECT attempt_id, generated_sql
                    FROM accepted_queries
                    WHERE id = CAST(:accepted_query_id AS uuid)
                    """
                ),
                {"accepted_query_id": initial["accepted_query_id"]},
            )
        ).one()
    assert after == before

    rows = await _audit_rows(async_engine_fixture, watermark)
    assert [(row["action_type"], row["outcome"]) for row in rows] == [
        (AuditActionType.QUERY_SUBMIT.value, "success"),
        (AuditActionType.QUERY_VALIDATE_PASS.value, "success"),
        (AuditActionType.QUERY_EXECUTE.value, "failure"),
    ]
    assert rows[-1]["context"] == {"reason": "execution_failed"}
    assert "source credential secret" not in json.dumps(rows)
    await _assert_chain_valid(async_engine_fixture)


async def test_persistence_failure_keeps_source_success_audit_without_history_mutation(
    authenticated_client,
    query_submit_payload,
    async_engine_fixture,
) -> None:
    _user_id, role_id = await _admin_identity(async_engine_fixture)
    await _set_quotas(authenticated_client, role_id, queries=100, executions=100)
    provider = _ProviderSpy()
    source = _SourceSpy()
    original_lookup = AcceptedQueryRepository.get_by_attempt_id

    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
        patch("app.source_db.adapters.PostgresAdapter.execute", new=source.execute),
    ):
        initial = await _submit_initial_attempt(authenticated_client, query_submit_payload, provider, source)
        async with async_engine_fixture.connect() as connection:
            before = (
                await connection.execute(
                    text(
                        """
                        SELECT attempt_id, generated_sql
                        FROM accepted_queries
                        WHERE id = CAST(:accepted_query_id AS uuid)
                        """
                    ),
                    {"accepted_query_id": initial["accepted_query_id"]},
                )
            ).one()
        watermark = await _audit_watermark(async_engine_fixture)
        lookup_calls = 0

        async def fail_persistence_lookup(repository, attempt_id, user_id):
            nonlocal lookup_calls
            lookup_calls += 1
            if lookup_calls == 2:
                raise RuntimeError("persistence detail")
            return await original_lookup(repository, attempt_id, user_id)

        with (
            patch.object(AcceptedQueryRepository, "get_by_attempt_id", new=fail_persistence_lookup),
            pytest.raises(RuntimeError, match="persistence detail"),
        ):
            await authenticated_client.post(
                "/api/v1/query/regenerate",
                json={"attempt_id": initial["attempt_id"]},
            )

    async with async_engine_fixture.connect() as connection:
        after = (
            await connection.execute(
                text(
                    """
                    SELECT attempt_id, generated_sql
                    FROM accepted_queries
                    WHERE id = CAST(:accepted_query_id AS uuid)
                    """
                ),
                {"accepted_query_id": initial["accepted_query_id"]},
            )
        ).one()
    assert after == before

    rows = await _audit_rows(async_engine_fixture, watermark)
    assert [(row["action_type"], row["outcome"]) for row in rows] == [
        (AuditActionType.QUERY_SUBMIT.value, "success"),
        (AuditActionType.QUERY_VALIDATE_PASS.value, "success"),
        (AuditActionType.QUERY_EXECUTE.value, "success"),
    ]
    assert "persistence detail" not in json.dumps(rows)
    await _assert_chain_valid(async_engine_fixture)
