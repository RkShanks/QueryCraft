"""IS-GAP-005 retry quota accounting through the public service API."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from fastapi import HTTPException

from app.core.attempt_store import EphemeralAttempt, store_attempt
from app.core.exceptions import QuotaExceededError, QuotaUnavailableError
from app.db.models.accepted_query import AcceptedQuery
from app.db.models.user import User
from app.evaluator.base import EvaluatorResult
from app.evaluator.schema_context import Column, SchemaContext, Table
from app.schemas.query import EvaluatorRejection
from app.services.query_service import QueryService, RolePolicy
from app.source_db.adapters import ExecuteResult
from tests.lifecycle.helpers import FakeRedis

USER_ID = "550e8400-e29b-41d4-a716-446655440000"
ROLE_ID = "660e8400-e29b-41d4-a716-446655440000"
CONNECTION_ID = "770e8400-e29b-41d4-a716-446655440000"
CHAT_SESSION_ID = "880e8400-e29b-41d4-a716-446655440000"
HTTP_SESSION_ID = "retry-quota-session"
PRIOR_ATTEMPT_ID = "prior-attempt"
RESET_AT = "2026-08-10T00:00:00+00:00"


class _ProviderSpy:
    def __init__(self, sql: str = "SELECT orders.id FROM orders") -> None:
        self.sql = sql
        self.calls = 0

    async def generate_sql(self, *_args, **_kwargs) -> str:
        self.calls += 1
        return self.sql


class _SourceSpy:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, _sql: str, _params: tuple = (), *, timeout: float | None = None) -> ExecuteResult:
        self.calls += 1
        return ExecuteResult(columns=["id"], rows=[(1,)])


class _Evaluator:
    async def evaluate(self, *_args, **_kwargs):
        return EvaluatorResult(passed=True)


def _user() -> User:
    return User(
        id=uuid.UUID(USER_ID),
        username="retry-user",
        display_name="Retry user",
        password_hash=None,
        role="admin",
        role_id=uuid.UUID(ROLE_ID),
        is_builtin=False,
        auth_provider="local",
    )


def _accepted_query() -> AcceptedQuery:
    return AcceptedQuery(
        id=uuid.uuid4(),
        user_id=uuid.UUID(USER_ID),
        database_connection_id=uuid.UUID(CONNECTION_ID),
        session_id=uuid.UUID(CHAT_SESSION_ID),
        question_text="Stored question",
        generated_sql="SELECT orders.id FROM orders",
        llm_provider="test",
        attempt_id="successor-attempt",
        saved=True,
        accepted_at=datetime(2026, 8, 9, tzinfo=UTC),
    )


def _service(*, quota: AsyncMock | None = None, policy_provider=None):
    database = AsyncMock()

    async def execute_statement(statement, *_args, **_kwargs):
        if "FROM users" in str(statement):
            return MagicMock(scalar_one_or_none=MagicMock(return_value=_user()))
        return MagicMock(fetchone=MagicMock(return_value=(3,)))

    database.execute = execute_statement
    repository = MagicMock()
    repository.get_by_attempt_id = AsyncMock(return_value=None)
    repository.create = AsyncMock(return_value=_accepted_query())
    session_repository = MagicMock()
    provider = _ProviderSpy()
    source = _SourceSpy()
    redis = FakeRedis()
    quota_service = quota if quota is not None else AsyncMock()
    if quota is None:
        quota_service.check_and_increment = AsyncMock()
    service = QueryService(
        accepted_query_repository=repository,
        session_repository=session_repository,
        db_session=database,
        redis=redis,
        llm=provider,
        evaluator=_Evaluator(),
        source_db_executor=AsyncMock(),
        source_db_adapter=source,
        llm_provider="test",
        schema_context=SchemaContext(tables=[Table(name="orders", columns=[Column(name="id")])]),
        target_dialect="postgres",
        connection_id=CONNECTION_ID,
        role_policy_provider=policy_provider,
        quota_service=quota_service,
    )
    return service, SimpleNamespace(
        database=database,
        repository=repository,
        provider=provider,
        source=source,
        quota=quota_service,
        redis=redis,
    )


async def _seed_attempt(service: QueryService, *, state: str = "EXECUTED", number: int = 1) -> None:
    prior = EphemeralAttempt(
        attempt_id=PRIOR_ATTEMPT_ID,
        session_id=HTTP_SESSION_ID,
        chat_session_id=CHAT_SESSION_ID,
        user_id=USER_ID,
        database_connection_id=uuid.UUID(CONNECTION_ID),
        sql="SELECT orders.id FROM orders WHERE orders.id > 0",
        question="Stored question",
        attempt_number=number,
        state=state,
    )
    await store_attempt(prior, HTTP_SESSION_ID, service._redis)
    await service._redis.set(f"active_attempt:{HTTP_SESSION_ID}", PRIOR_ATTEMPT_ID)


async def _retry(service: QueryService, decision: str):
    if decision == "regenerate":
        return await service.regenerate_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID)
    return await service.reject_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID)


def _quota_error(dimension: str, availability: str) -> BaseException:
    if availability == "unavailable":
        return QuotaUnavailableError()
    return QuotaExceededError(dimension=dimension, reset_at=RESET_AT)


@pytest.mark.parametrize("decision", ["regenerate", "reject"])
async def test_retry_under_quota_charges_each_external_invocation_once(decision: str) -> None:
    service, dependencies = _service()
    await _seed_attempt(service)

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock):
        response = await _retry(service, decision)

    assert response.kind == "result"
    assert dependencies.quota.check_and_increment.await_args_list == [
        call(uuid.UUID(USER_ID), uuid.UUID(ROLE_ID), "queries"),
        call(uuid.UUID(USER_ID), uuid.UUID(ROLE_ID), "executions"),
    ]
    assert dependencies.provider.calls == 1
    assert dependencies.source.calls == 1


@pytest.mark.parametrize("decision", ["regenerate", "reject"])
@pytest.mark.parametrize("counter_state", ["at_limit", "over_limit"])
async def test_retry_query_quota_denial_stops_before_provider(
    decision: str,
    counter_state: str,
) -> None:
    quota = AsyncMock()
    quota.check_and_increment = AsyncMock(side_effect=_quota_error("queries", counter_state))
    service, dependencies = _service(quota=quota)
    await _seed_attempt(service)

    with (
        patch("app.services.query_service.AuditService.log", new_callable=AsyncMock),
        pytest.raises(HTTPException) as exc_info,
    ):
        await _retry(service, decision)

    assert exc_info.value.status_code == 429
    assert dependencies.quota.check_and_increment.await_count == 1
    assert dependencies.provider.calls == 0
    assert dependencies.source.calls == 0
    dependencies.repository.create.assert_not_awaited()


@pytest.mark.parametrize("decision", ["regenerate", "reject"])
async def test_retry_query_quota_unavailable_fails_closed(decision: str) -> None:
    quota = AsyncMock()
    quota.check_and_increment = AsyncMock(side_effect=_quota_error("queries", "unavailable"))
    service, dependencies = _service(quota=quota)
    await _seed_attempt(service)

    with (
        patch("app.services.query_service.AuditService.log", new_callable=AsyncMock),
        pytest.raises(HTTPException) as exc_info,
    ):
        await _retry(service, decision)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == {
        "error": "service_unavailable",
        "message_key": "error.service_unavailable",
    }
    assert dependencies.provider.calls == 0
    assert dependencies.source.calls == 0


@pytest.mark.parametrize("availability", ["at_limit", "over_limit", "unavailable"])
async def test_retry_execution_quota_denial_stops_after_one_provider_call(availability: str) -> None:
    quota = AsyncMock()
    quota.check_and_increment = AsyncMock(side_effect=[None, _quota_error("executions", availability)])
    service, dependencies = _service(quota=quota)
    await _seed_attempt(service)

    with (
        patch("app.services.query_service.AuditService.log", new_callable=AsyncMock),
        pytest.raises(HTTPException) as exc_info,
    ):
        await service.regenerate_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID)

    assert exc_info.value.status_code == (503 if availability == "unavailable" else 429)
    assert dependencies.quota.check_and_increment.await_count == 2
    assert dependencies.provider.calls == 1
    assert dependencies.source.calls == 0
    dependencies.repository.create.assert_not_awaited()


@pytest.mark.parametrize(
    ("state", "attempt_number"),
    [("PENDING", 1), ("EXECUTED", 4)],
)
async def test_invalid_state_and_retry_limit_charge_nothing(state: str, attempt_number: int) -> None:
    service, dependencies = _service()
    await _seed_attempt(service, state=state, number=attempt_number)

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock):
        if state == "PENDING":
            with pytest.raises(HTTPException) as exc_info:
                await service.regenerate_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID)
            assert exc_info.value.status_code == 422
        else:
            response = await service.regenerate_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID)
            assert response.kind == "refine"

    dependencies.quota.check_and_increment.assert_not_awaited()
    assert dependencies.provider.calls == 0
    assert dependencies.source.calls == 0


async def test_current_policy_denial_before_provider_charges_nothing() -> None:
    async def deny_all_policy(_user_id: uuid.UUID, connection_id: uuid.UUID) -> RolePolicy:
        return RolePolicy(
            user_id=uuid.UUID(USER_ID),
            role_id=uuid.UUID(ROLE_ID),
            connection_id=connection_id,
            allowed_tables=[],
        )

    service, dependencies = _service(policy_provider=deny_all_policy)
    await _seed_attempt(service)

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock):
        response = await service.regenerate_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID)

    assert isinstance(response, EvaluatorRejection)
    dependencies.quota.check_and_increment.assert_not_awaited()
    assert dependencies.provider.calls == 0
    assert dependencies.source.calls == 0
