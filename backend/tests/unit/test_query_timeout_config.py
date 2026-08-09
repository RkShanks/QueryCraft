"""IS-GAP-004 end-to-end query deadline behavior."""

import asyncio
import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.attempt_store import EphemeralAttempt, store_attempt
from app.core.exceptions import LLMTimeout
from app.db.models.accepted_query import AcceptedQuery
from app.db.models.enums import AuditActionType
from app.db.models.session import Session
from app.db.models.user import User
from app.evaluator.schema_context import Column, SchemaContext, Table
from app.services.query_service import QueryService, RolePolicy
from app.source_db.adapters import ExecuteResult
from tests.lifecycle.helpers import FakeRedis

USER_ID = "550e8400-e29b-41d4-a716-446655440000"
CONNECTION_ID = "770e8400-e29b-41d4-a716-446655440000"
CHAT_SESSION_ID = "880e8400-e29b-41d4-a716-446655440000"
ACCEPTED_QUERY_ID = "aaaaaaaa-0000-0000-0000-000000000001"
TIMEOUT_DETAIL = {"error": "timeout", "message_key": "error.timeout"}


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _RecordingRedis(FakeRedis):
    def __init__(self) -> None:
        super().__init__()
        self.set_calls: list[dict] = []

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        self.set_calls.append({"key": key, "value": value, "nx": nx, "ex": ex})
        return await super().set(key, value, nx=nx, ex=ex)


class _Provider:
    def __init__(self, sql: str = "SELECT orders.id FROM orders") -> None:
        self.sql = sql
        self.calls = 0

    async def generate_sql(self, *_args, **_kwargs) -> str:
        self.calls += 1
        return self.sql


class _SlowProvider:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.cancelled = asyncio.Event()

    async def generate_sql(self, *_args, **_kwargs) -> str:
        self.task = asyncio.current_task()
        try:
            await asyncio.Event().wait()
        finally:
            self.cancelled.set()


class _AdvancingProvider:
    def __init__(self, clock: _Clock, seconds: float) -> None:
        self.clock = clock
        self.seconds = seconds

    async def generate_sql(self, *_args, **_kwargs) -> str:
        self.clock.advance(self.seconds)
        return "SELECT orders.id FROM orders"


class _Evaluator:
    def __init__(self, clock: _Clock | None = None, seconds: float = 0) -> None:
        self.clock = clock
        self.seconds = seconds

    async def evaluate(self, *_args, **_kwargs):
        if self.clock is not None:
            self.clock.advance(self.seconds)
        return SimpleNamespace(passed=True, violations=[])


class _Adapter:
    def __init__(self, clock: _Clock | None = None, seconds: float = 0) -> None:
        self.clock = clock
        self.seconds = seconds
        self.timeouts: list[float | None] = []

    async def execute(self, _sql: str, _params: tuple = (), *, timeout: float | None = None) -> ExecuteResult:
        self.timeouts.append(timeout)
        if self.clock is not None:
            self.clock.advance(self.seconds)
        return ExecuteResult(columns=["id"], rows=[(1,)])


class _SlowAdapter:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.cancelled = asyncio.Event()

    async def execute(self, _sql: str, _params: tuple = (), *, timeout: float | None = None) -> ExecuteResult:
        self.task = asyncio.current_task()
        try:
            await asyncio.Event().wait()
        finally:
            self.cancelled.set()


class _RaisingAdapter:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    async def execute(self, _sql: str, _params: tuple = (), *, timeout: float | None = None) -> ExecuteResult:
        raise self.error


class _AdvancingMaskPolicy:
    def __init__(self, clock: _Clock, seconds: float) -> None:
        self.clock = clock
        self.seconds = seconds

    def apply_column_masks(self, query_result, _masks, *, dialect=None):
        self.clock.advance(self.seconds)
        return query_result


class _AdvancingQuota:
    def __init__(self, clock: _Clock, seconds: float) -> None:
        self.clock = clock
        self.seconds = seconds

    async def check_and_increment(self, *_args, **_kwargs) -> None:
        self.clock.advance(self.seconds)


def _accepted_query() -> AcceptedQuery:
    return AcceptedQuery(
        id=uuid.UUID(ACCEPTED_QUERY_ID),
        user_id=uuid.UUID(USER_ID),
        generated_sql="SELECT orders.id FROM orders",
        question_text="Stored question",
        llm_provider="test",
        database_connection_id=uuid.UUID(CONNECTION_ID),
        session_id=uuid.UUID(CHAT_SESSION_ID),
        accepted_at=datetime(2026, 8, 9, tzinfo=UTC),
    )


def _build_service(
    *,
    timeout_seconds: int,
    clock=None,
    provider=None,
    evaluator=None,
    adapter=None,
    policy=None,
    role_policy_provider=None,
    quota_service=None,
):
    redis = _RecordingRedis()
    database = AsyncMock()
    user = User(
        id=uuid.UUID(USER_ID),
        username="deadline-user",
        display_name="Deadline user",
        password_hash=None,
        role="admin",
        role_id=uuid.uuid4() if quota_service is not None else None,
        is_builtin=False,
        auth_provider="local",
    )

    async def execute_statement(statement, *_args, **_kwargs):
        if "FROM users" in str(statement):
            return MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        return MagicMock(fetchone=MagicMock(return_value=(3,)))

    database.execute = execute_statement
    database.flush = AsyncMock()

    saved_query = AcceptedQuery(
        id=uuid.UUID(ACCEPTED_QUERY_ID),
        user_id=uuid.UUID(USER_ID),
        session_id=uuid.UUID(CHAT_SESSION_ID),
        accepted_at=datetime(2026, 8, 9, tzinfo=UTC),
        question_text="Stored question",
        generated_sql="SELECT orders.id FROM orders",
        llm_provider="test",
        database_connection_id=uuid.UUID(CONNECTION_ID),
    )
    repository = MagicMock()
    repository.list_by_session = AsyncMock(return_value=[])
    repository.get_latest_by_session = AsyncMock(return_value=None)
    repository.get_by_attempt_id = AsyncMock(return_value=None)
    repository.get_by_id = AsyncMock(return_value=_accepted_query())
    repository.create = AsyncMock(return_value=saved_query)

    chat_session = Session(
        id=uuid.UUID(CHAT_SESSION_ID),
        user_id=uuid.UUID(USER_ID),
        connection_id=uuid.UUID(CONNECTION_ID),
        preview_text="Existing",
    )
    session_repository = MagicMock()
    session_repository.get_by_id = AsyncMock(return_value=chat_session)
    session_repository.create = AsyncMock(return_value=chat_session)
    session_repository.update_last_activity = AsyncMock(return_value=True)
    session_repository.update_preview_text = AsyncMock(return_value=True)

    service = QueryService(
        accepted_query_repository=repository,
        session_repository=session_repository,
        db_session=database,
        redis=redis,
        llm=provider or _Provider(),
        evaluator=evaluator or _Evaluator(),
        source_db_executor=AsyncMock(),
        source_db_adapter=adapter or _Adapter(),
        llm_provider="test",
        schema_context=SchemaContext(tables=[Table(name="orders", columns=[Column(name="id")])]),
        target_dialect="postgres",
        connection_id=CONNECTION_ID,
        policy_enforcement=policy,
        role_policy_provider=role_policy_provider,
        quota_service=quota_service,
        query_timeout_seconds=timeout_seconds,
        monotonic_clock=clock,
    )
    return service, SimpleNamespace(redis=redis, database=database, repository=repository)


async def _seed_regenerate(service: QueryService) -> EphemeralAttempt:
    prior = EphemeralAttempt(
        attempt_id="prior-attempt",
        session_id="http-session",
        chat_session_id=CHAT_SESSION_ID,
        user_id=USER_ID,
        database_connection_id=uuid.UUID(CONNECTION_ID),
        sql="SELECT 0",
        question="Stored question",
        state="EXECUTED",
    )
    await store_attempt(prior, "http-session", service._redis)
    await service._redis.set("active_attempt:http-session", prior.attempt_id)
    return prior


async def _invoke_operation(service: QueryService, operation: str):
    if operation == "submit":
        return await service.submit_question(
            http_session_id="http-session",
            user_id=USER_ID,
            question="Deadline behavior",
            chat_session_id=CHAT_SESSION_ID,
        )
    if operation == "regenerate":
        prior = await _seed_regenerate(service)
        return await service.regenerate_query(prior.attempt_id, "http-session", USER_ID)
    if operation == "rerun":
        return await service.rerun_accepted_query(ACCEPTED_QUERY_ID, USER_ID, CONNECTION_ID)
    pytest.fail(f"unsupported operation: {operation}")


async def _capture_timeout(awaitable) -> HTTPException:
    with pytest.raises(HTTPException) as exc_info:
        await awaitable
    assert exc_info.value.status_code == 504
    assert exc_info.value.detail == TIMEOUT_DETAIL
    return exc_info.value


def _timeout_failure_calls(audit_mock: AsyncMock) -> list:
    return [
        call
        for call in audit_mock.await_args_list
        if call.kwargs.get("outcome") == "failure" and call.kwargs.get("context") == {"reason": "timeout"}
    ]


@pytest.fixture(autouse=True)
def _allow_detection(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.query_service.DetectionConfigRepository.get_for_detection",
        AsyncMock(return_value=SimpleNamespace(block_confidence=0.8, flag_confidence=0.5)),
    )
    monkeypatch.setattr(
        "app.services.query_service.HostileInputDetector.detect",
        AsyncMock(return_value=SimpleNamespace(outcome="allowed", results=[])),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["submit", "regenerate", "rerun"])
async def test_non_default_short_deadline_times_out_every_query_operation(operation: str) -> None:
    slow_provider = _SlowProvider() if operation != "rerun" else None
    slow_adapter = _SlowAdapter() if operation == "rerun" else _Adapter()
    service, dependencies = _build_service(
        timeout_seconds=1,
        provider=slow_provider,
        adapter=slow_adapter,
    )

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock) as audit_mock:
        await _capture_timeout(_invoke_operation(service, operation))

    assert len(_timeout_failure_calls(audit_mock)) == 1
    assert not any(key.startswith("processing_lock:") for key in dependencies.redis._data)
    assert "active_attempt:http-session" not in dependencies.redis._data
    attempts = [json.loads(raw) for key, raw in dependencies.redis._data.items() if key.startswith("attempt:")]
    if operation == "rerun":
        assert attempts == []
    else:
        assert [attempt["state"] for attempt in attempts] == ["TIMEOUT"]
    if slow_provider is not None:
        assert slow_provider.cancelled.is_set()
        assert slow_provider.task is not None and slow_provider.task.done()
    if isinstance(slow_adapter, _SlowAdapter):
        assert slow_adapter.cancelled.is_set()
        assert slow_adapter.task is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["submit", "regenerate", "rerun"])
async def test_processing_lock_uses_deadline_plus_cleanup_grace(operation: str) -> None:
    service, dependencies = _build_service(timeout_seconds=7)

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock):
        await _invoke_operation(service, operation)

    lock_calls = [call for call in dependencies.redis.set_calls if call["key"].startswith("processing_lock:")]
    assert len(lock_calls) == 1
    assert lock_calls[0]["ex"] == 12


@pytest.mark.asyncio
async def test_earlier_stage_consumption_reduces_source_budget_without_thirty_second_cap() -> None:
    clock = _Clock()
    adapter = _Adapter()
    service, _ = _build_service(
        timeout_seconds=60,
        clock=clock,
        provider=_AdvancingProvider(clock, 5),
        adapter=adapter,
    )

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock):
        await _invoke_operation(service, "submit")

    assert adapter.timeouts == [pytest.approx(55)]
    assert adapter.timeouts[0] > 30


@pytest.mark.asyncio
async def test_provider_timeout_uses_sanitized_operation_timeout_contract() -> None:
    provider = AsyncMock(generate_sql=AsyncMock(side_effect=LLMTimeout(provider="test", timeout_s=5)))
    service, _ = _build_service(timeout_seconds=5, provider=provider)

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock) as audit_mock:
        await _capture_timeout(_invoke_operation(service, "submit"))

    assert len(_timeout_failure_calls(audit_mock)) == 1


@pytest.mark.asyncio
async def test_detection_consuming_deadline_stops_before_quota_and_provider(monkeypatch) -> None:
    clock = _Clock()
    provider = _Provider()
    quota = AsyncMock()

    async def detect_then_expire(*_args, **_kwargs):
        clock.advance(11)
        return SimpleNamespace(outcome="allowed", results=[])

    monkeypatch.setattr(
        "app.services.query_service.HostileInputDetector.detect",
        detect_then_expire,
    )
    service, _ = _build_service(
        timeout_seconds=10,
        clock=clock,
        provider=provider,
        quota_service=quota,
    )

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock):
        await _capture_timeout(_invoke_operation(service, "submit"))

    quota.check_and_increment.assert_not_awaited()
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_quota_consuming_deadline_stops_before_provider() -> None:
    clock = _Clock()
    provider = _Provider()
    service, _ = _build_service(
        timeout_seconds=10,
        clock=clock,
        provider=provider,
        quota_service=_AdvancingQuota(clock, 11),
    )

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock):
        await _capture_timeout(_invoke_operation(service, "submit"))

    assert provider.calls == 0


@pytest.mark.asyncio
async def test_policy_consuming_deadline_stops_before_provider() -> None:
    clock = _Clock()
    provider = _Provider()
    policy = RolePolicy(
        user_id=uuid.UUID(USER_ID),
        role_id=uuid.uuid4(),
        connection_id=uuid.UUID(CONNECTION_ID),
        allowed_tables=[{"table": "orders", "columns": ["id"]}],
    )

    async def slow_policy_provider(_user_id, _connection_id):
        clock.advance(11)
        return policy

    service, _ = _build_service(
        timeout_seconds=10,
        clock=clock,
        provider=provider,
        role_policy_provider=slow_policy_provider,
    )

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock):
        await _capture_timeout(_invoke_operation(service, "submit"))

    assert provider.calls == 0


@pytest.mark.asyncio
async def test_evaluator_consuming_deadline_prevents_source_and_history_success() -> None:
    clock = _Clock()
    service, dependencies = _build_service(
        timeout_seconds=10,
        clock=clock,
        evaluator=_Evaluator(clock, 11),
    )

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock) as audit_mock:
        await _capture_timeout(_invoke_operation(service, "submit"))

    dependencies.repository.create.assert_not_awaited()
    assert len(_timeout_failure_calls(audit_mock)) == 1


@pytest.mark.asyncio
async def test_source_timeout_has_one_failure_audit_and_truthful_attempt_state() -> None:
    service, dependencies = _build_service(
        timeout_seconds=10,
        adapter=_RaisingAdapter(TimeoutError()),
    )

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock) as audit_mock:
        await _capture_timeout(_invoke_operation(service, "submit"))

    attempts = [json.loads(raw) for key, raw in dependencies.redis._data.items() if key.startswith("attempt:")]
    assert [attempt["state"] for attempt in attempts] == ["TIMEOUT"]
    assert len(_timeout_failure_calls(audit_mock)) == 1
    assert not any(
        call.kwargs.get("action") == AuditActionType.QUERY_EXECUTE and call.kwargs.get("outcome") == "success"
        for call in audit_mock.await_args_list
    )


@pytest.mark.asyncio
async def test_masking_consuming_deadline_prevents_persistence() -> None:
    clock = _Clock()
    role_policy = RolePolicy(
        user_id=uuid.UUID(USER_ID),
        role_id=uuid.uuid4(),
        connection_id=uuid.UUID(CONNECTION_ID),
        allowed_tables=[{"table": "orders", "columns": ["id"]}],
        column_masks=[{"table": "orders", "column": "id", "mask_type": "full"}],
    )

    async def policy_provider(_user_id, _connection_id):
        return role_policy

    service, dependencies = _build_service(
        timeout_seconds=10,
        clock=clock,
        policy=_AdvancingMaskPolicy(clock, 11),
        role_policy_provider=policy_provider,
    )

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock):
        await _capture_timeout(_invoke_operation(service, "submit"))

    dependencies.repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_persistence_boundary_expiry_rolls_back_without_success() -> None:
    clock = _Clock()
    service, dependencies = _build_service(timeout_seconds=10, clock=clock)
    saved_query = dependencies.repository.create.return_value

    async def create_then_expire(**_kwargs):
        clock.advance(11)
        return saved_query

    dependencies.repository.create.side_effect = create_then_expire

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock) as audit_mock:
        await _capture_timeout(_invoke_operation(service, "submit"))

    dependencies.database.rollback.assert_awaited()
    assert len(_timeout_failure_calls(audit_mock)) == 1


@pytest.mark.asyncio
async def test_success_audit_boundary_expiry_rolls_back_and_records_one_timeout() -> None:
    clock = _Clock()
    service, dependencies = _build_service(timeout_seconds=10, clock=clock)

    async def expire_during_success_audit(*_args, **kwargs):
        if kwargs.get("action") == AuditActionType.QUERY_EXECUTE and kwargs.get("outcome") == "success":
            clock.advance(11)

    audit_mock = AsyncMock(side_effect=expire_during_success_audit)
    with patch("app.services.query_service.AuditService.log", new=audit_mock):
        await _capture_timeout(_invoke_operation(service, "submit"))

    dependencies.database.rollback.assert_awaited()
    assert len(_timeout_failure_calls(audit_mock)) == 1


@pytest.mark.asyncio
async def test_timeout_cleanup_never_deletes_replacement_lock_owner() -> None:
    clock = _Clock()

    class ReplacementAdapter(_Adapter):
        def __init__(self) -> None:
            super().__init__()
            self.redis: _RecordingRedis | None = None

        async def execute(self, _sql, _params=(), *, timeout=None):
            assert self.redis is not None
            await self.redis.set("processing_lock:http-session", "replacement-owner")
            clock.advance(11)
            return ExecuteResult(columns=["id"], rows=[(1,)])

    adapter = ReplacementAdapter()
    service, dependencies = _build_service(timeout_seconds=10, clock=clock, adapter=adapter)
    adapter.redis = dependencies.redis

    with patch("app.services.query_service.AuditService.log", new_callable=AsyncMock):
        await _capture_timeout(_invoke_operation(service, "submit"))

    assert await dependencies.redis.get("processing_lock:http-session") == "replacement-owner"
