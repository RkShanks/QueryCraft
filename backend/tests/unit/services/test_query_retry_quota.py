"""IS-GAP-005 retry quota accounting through the public service API."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from fastapi import HTTPException

from app.core.attempt_store import EphemeralAttempt, store_attempt
from app.core.exceptions import (
    LLMTimeout,
    PolicySchemaConflictError,
    QuotaExceededError,
    QuotaUnavailableError,
    SourceDBTimeout,
)
from app.db.models.accepted_query import AcceptedQuery
from app.db.models.enums import AuditActionType
from app.db.models.user import User
from app.evaluator.base import EvaluatorResult, EvaluatorViolation
from app.evaluator.schema_context import Column, SchemaContext, Table
from app.schemas.query import EvaluatorRejection
from app.services.policy_enforcement import PolicyEnforcementService
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


def _service(
    *,
    quota: AsyncMock | None = None,
    policy_provider=None,
    provider=None,
    evaluator=None,
    source=None,
    policy=None,
):
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
    provider_spy = provider or _ProviderSpy()
    source_spy = source or _SourceSpy()
    redis = FakeRedis()
    quota_service = quota if quota is not None else AsyncMock()
    if quota is None:
        quota_service.check_and_increment = AsyncMock()
    service = QueryService(
        accepted_query_repository=repository,
        session_repository=session_repository,
        db_session=database,
        redis=redis,
        llm=provider_spy,
        evaluator=evaluator or _Evaluator(),
        source_db_executor=AsyncMock(),
        source_db_adapter=source_spy,
        llm_provider="test",
        schema_context=SchemaContext(tables=[Table(name="orders", columns=[Column(name="id")])]),
        target_dialect="postgres",
        connection_id=CONNECTION_ID,
        policy_enforcement=policy,
        role_policy_provider=policy_provider,
        quota_service=quota_service,
    )
    return service, SimpleNamespace(
        database=database,
        repository=repository,
        provider=provider_spy,
        source=source_spy,
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


def _audit_contract(audit: AsyncMock) -> list[tuple[AuditActionType, str, str | None, dict]]:
    return [
        (
            call_args.kwargs["action"],
            call_args.kwargs["outcome"],
            call_args.kwargs.get("resource_id"),
            call_args.kwargs.get("context") or {},
        )
        for call_args in audit.await_args_list
    ]


class _FailingEvaluator:
    async def evaluate(self, *_args, **_kwargs) -> EvaluatorResult:
        return EvaluatorResult(
            passed=False,
            violations=[EvaluatorViolation(rule_name="schema_validation", message_key="error.validation")],
        )


class _RaisingProvider(_ProviderSpy):
    def __init__(self, error: BaseException) -> None:
        super().__init__()
        self.error = error

    async def generate_sql(self, *_args, **_kwargs) -> str:
        self.calls += 1
        raise self.error


class _RaisingSource(_SourceSpy):
    def __init__(self, error: BaseException) -> None:
        super().__init__()
        self.error = error

    async def execute(self, _sql: str, _params: tuple = (), *, timeout: float | None = None) -> ExecuteResult:
        self.calls += 1
        raise self.error


class _SchemaConflictPolicy(PolicyEnforcementService):
    def apply_row_filters(self, **_kwargs):
        raise PolicySchemaConflictError()


class _MaskingFailurePolicy(PolicyEnforcementService):
    def apply_column_masks(self, *_args, **_kwargs):
        raise RuntimeError("sensitive masking failure")


async def _allowing_policy(*_args) -> RolePolicy:
    return RolePolicy(
        user_id=uuid.UUID(USER_ID),
        role_id=uuid.UUID(ROLE_ID),
        connection_id=uuid.UUID(CONNECTION_ID),
        allowed_tables=[{"table": "orders", "columns": ["id"]}],
    )


@pytest.mark.parametrize("decision", ["regenerate", "reject"])
async def test_successful_retry_emits_one_ordered_lifecycle(decision: str) -> None:
    service, _dependencies = _service(policy_provider=_allowing_policy)
    await _seed_attempt(service)

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock) as audit:
        await _retry(service, decision)

    lifecycle = _audit_contract(audit)
    expected_actions = [
        AuditActionType.QUERY_SUBMIT,
        AuditActionType.QUERY_VALIDATE_PASS,
        AuditActionType.QUERY_EXECUTE,
    ]
    if decision == "reject":
        expected_actions.insert(0, AuditActionType.QUERY_REJECT)
    assert [event[0] for event in lifecycle] == expected_actions
    retry_events = lifecycle[1:] if decision == "reject" else lifecycle
    assert {event[2] for event in retry_events} == {retry_events[0][2]}
    assert retry_events[0][2] not in (None, PRIOR_ATTEMPT_ID)
    assert [(event[1], event[3]) for event in retry_events] == [
        ("success", {}),
        ("success", {}),
        ("success", {}),
    ]


@pytest.mark.parametrize(
    ("provider_sql", "evaluator", "reason"),
    [
        ("SELECT orders.id FROM orders", _FailingEvaluator(), "evaluator_rejected"),
        ("SELECT orders.id FROM orders WHERE orders.id > 0", _Evaluator(), "duplicate_candidate"),
    ],
)
async def test_retry_candidate_rejection_emits_submit_then_validate_failure(
    provider_sql: str,
    evaluator,
    reason: str,
) -> None:
    service, dependencies = _service(provider=_ProviderSpy(provider_sql), evaluator=evaluator)
    await _seed_attempt(service)

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock) as audit:
        response = await service.regenerate_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID)

    assert response.kind == "refine"
    assert dependencies.source.calls == 0
    lifecycle = _audit_contract(audit)
    assert [(event[0], event[1]) for event in lifecycle] == [
        (AuditActionType.QUERY_SUBMIT, "success"),
        (AuditActionType.QUERY_VALIDATE_FAIL, "failure"),
    ]
    assert lifecycle[-1][3] == {"reason": reason}
    assert lifecycle[0][2] == lifecycle[1][2]


async def test_role_authorization_denial_emits_validate_pass_then_access_denied() -> None:
    async def restricted_policy(*_args) -> RolePolicy:
        return RolePolicy(
            user_id=uuid.UUID(USER_ID),
            role_id=uuid.UUID(ROLE_ID),
            connection_id=uuid.UUID(CONNECTION_ID),
            allowed_tables=[{"table": "reports", "columns": ["id"]}],
        )

    service, dependencies = _service(policy_provider=restricted_policy)
    await _seed_attempt(service)

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock) as audit:
        response = await service.regenerate_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID)

    assert response.kind == "refine"
    assert dependencies.source.calls == 0
    assert [(event[0], event[1], event[3]) for event in _audit_contract(audit)] == [
        (AuditActionType.QUERY_SUBMIT, "success", {}),
        (AuditActionType.QUERY_VALIDATE_PASS, "success", {}),
        (AuditActionType.ACCESS_DENIED, "denied", {"reason": "role_authorization"}),
    ]


async def test_row_filter_schema_conflict_emits_sanitized_policy_failure() -> None:
    async def row_filter_policy(*_args) -> RolePolicy:
        policy = await _allowing_policy()
        return RolePolicy(
            user_id=policy.user_id,
            role_id=policy.role_id,
            connection_id=policy.connection_id,
            allowed_tables=policy.allowed_tables,
            row_filters=[{"table": "orders", "filter": "missing = 1"}],
        )

    service, dependencies = _service(
        policy_provider=row_filter_policy,
        policy=_SchemaConflictPolicy(),
    )
    await _seed_attempt(service)

    with (
        patch("app.services.query_service.AuditService.log", new_callable=AsyncMock) as audit,
        pytest.raises(HTTPException) as exc_info,
    ):
        await service.regenerate_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID)

    assert exc_info.value.status_code == 409
    assert dependencies.source.calls == 0
    assert [(event[0], event[3]) for event in _audit_contract(audit)] == [
        (AuditActionType.QUERY_SUBMIT, {}),
        (AuditActionType.QUERY_VALIDATE_PASS, {}),
        (AuditActionType.POLICY_SCHEMA_MISMATCH, {"reason": "policy_schema_conflict"}),
    ]


@pytest.mark.parametrize(
    ("error", "expected_status", "reason"),
    [
        (RuntimeError("provider secret"), 502, "provider_failure"),
        (LLMTimeout("provider secret"), 504, "timeout"),
    ],
)
async def test_provider_failure_emits_one_sanitized_submit_failure(
    error: BaseException,
    expected_status: int,
    reason: str,
) -> None:
    service, dependencies = _service(provider=_RaisingProvider(error))
    await _seed_attempt(service)

    with (
        patch("app.services.query_service.AuditService.log", new_callable=AsyncMock) as audit,
        pytest.raises(HTTPException) as exc_info,
    ):
        await service.regenerate_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID)

    assert exc_info.value.status_code == expected_status
    assert "provider secret" not in str(exc_info.value.detail)
    assert dependencies.provider.calls == 1
    assert dependencies.source.calls == 0
    assert [(event[0], event[1], event[3]) for event in _audit_contract(audit)] == [
        (AuditActionType.QUERY_SUBMIT, "failure", {"reason": reason}),
    ]


@pytest.mark.parametrize(
    ("error", "expected_status", "reason"),
    [
        (RuntimeError("source secret"), 502, "execution_failed"),
        (SourceDBTimeout(999), 504, "timeout"),
    ],
)
async def test_source_failure_emits_failed_execute_after_successful_validation(
    error: BaseException,
    expected_status: int,
    reason: str,
) -> None:
    service, dependencies = _service(source=_RaisingSource(error))
    await _seed_attempt(service)

    with (
        patch("app.services.query_service.AuditService.log", new_callable=AsyncMock) as audit,
        pytest.raises(HTTPException) as exc_info,
    ):
        await service.regenerate_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID)

    assert exc_info.value.status_code == expected_status
    assert "source secret" not in str(exc_info.value.detail)
    assert dependencies.provider.calls == 1
    assert dependencies.source.calls == 1
    assert [(event[0], event[1], event[3]) for event in _audit_contract(audit)] == [
        (AuditActionType.QUERY_SUBMIT, "success", {}),
        (AuditActionType.QUERY_VALIDATE_PASS, "success", {}),
        (AuditActionType.QUERY_EXECUTE, "failure", {"reason": reason}),
    ]


async def test_masking_failure_emits_failed_execute_without_history() -> None:
    async def masked_policy(*_args) -> RolePolicy:
        policy = await _allowing_policy()
        return RolePolicy(
            user_id=policy.user_id,
            role_id=policy.role_id,
            connection_id=policy.connection_id,
            allowed_tables=policy.allowed_tables,
            column_masks=[{"table": "orders", "column": "id", "mask_type": "full"}],
        )

    service, dependencies = _service(
        policy_provider=masked_policy,
        policy=_MaskingFailurePolicy(),
    )
    await _seed_attempt(service)

    with (
        patch("app.services.query_service.AuditService.log", new_callable=AsyncMock) as audit,
        pytest.raises(HTTPException) as exc_info,
    ):
        await service.regenerate_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID)

    assert exc_info.value.status_code == 502
    dependencies.repository.create.assert_not_awaited()
    assert _audit_contract(audit)[-1][0:2] == (AuditActionType.QUERY_EXECUTE, "failure")
    assert _audit_contract(audit)[-1][3] == {"reason": "result_processing_failed"}


async def test_success_audit_precedes_persistence_failure_and_history_rolls_back() -> None:
    service, dependencies = _service()
    dependencies.repository.create.side_effect = RuntimeError("persistence secret")
    await _seed_attempt(service)

    with (
        patch("app.services.query_service.AuditService.log", new_callable=AsyncMock) as audit,
        pytest.raises(RuntimeError, match="persistence secret"),
    ):
        await service.regenerate_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID)

    assert [event[0:2] for event in _audit_contract(audit)] == [
        (AuditActionType.QUERY_SUBMIT, "success"),
        (AuditActionType.QUERY_VALIDATE_PASS, "success"),
        (AuditActionType.QUERY_EXECUTE, "success"),
    ]
    dependencies.database.rollback.assert_awaited()


async def test_success_audit_failure_is_fail_closed_before_persistence() -> None:
    service, dependencies = _service()
    await _seed_attempt(service)

    async def fail_execute_audit(_session, *, action, outcome, **_kwargs):
        if action == AuditActionType.QUERY_EXECUTE and outcome == "success":
            raise RuntimeError("audit unavailable")

    with (
        patch("app.services.query_service.AuditService.log", side_effect=fail_execute_audit),
        pytest.raises(RuntimeError, match="audit unavailable"),
    ):
        await service.regenerate_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID)

    dependencies.repository.create.assert_not_awaited()


async def test_concurrent_reject_records_one_decision_and_one_retry_lifecycle() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    class BlockingProvider(_ProviderSpy):
        async def generate_sql(self, *_args, **_kwargs) -> str:
            self.calls += 1
            entered.set()
            await release.wait()
            return self.sql

    service, dependencies = _service(provider=BlockingProvider())
    await _seed_attempt(service)

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock) as audit:
        winner = asyncio.create_task(service.reject_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID))
        await entered.wait()
        with pytest.raises(HTTPException) as loser:
            await service.reject_query(PRIOR_ATTEMPT_ID, HTTP_SESSION_ID, USER_ID)
        release.set()
        await winner

    assert loser.value.status_code == 409
    assert dependencies.provider.calls == 1
    assert [event[0] for event in _audit_contract(audit)].count(AuditActionType.QUERY_REJECT) == 1
