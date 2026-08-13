"""Operational liveness and readiness HTTP contract regressions."""

import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.readiness import ReadinessState
from app.main import create_app


@pytest.fixture
def probe_app(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    get_settings.cache_clear()
    return create_app()


class ProbeQueryRows:
    def __init__(self, rows: list[tuple[int, str]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[int, str]]:
        return self._rows


class PlatformDatabaseBoundary:
    def __init__(self, revision: str = "head") -> None:
        self.revision = revision
        self.delay_seconds = 0.0
        self.failure: Exception | None = None
        self.active_checks = 0
        self.maximum_active_checks = 0

    def connect(self):
        return PlatformConnectionBoundary(self)


class PlatformConnectionBoundary:
    def __init__(self, database: PlatformDatabaseBoundary) -> None:
        self._database = database

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _traceback) -> None:
        return None

    async def execution_options(self, **_options):
        return self

    async def execute(self, _statement) -> ProbeQueryRows:
        self._database.active_checks += 1
        self._database.maximum_active_checks = max(
            self._database.maximum_active_checks,
            self._database.active_checks,
        )
        try:
            await asyncio.sleep(self._database.delay_seconds)
            if self._database.failure is not None:
                raise self._database.failure
            return ProbeQueryRows([(1, self._database.revision)])
        finally:
            self._database.active_checks -= 1


class RedisBoundary:
    def __init__(self) -> None:
        self.ping_response: object = True
        self.delay_seconds = 0.0
        self.failure: Exception | None = None
        self.active_checks = 0
        self.maximum_active_checks = 0

    async def ping(self):
        self.active_checks += 1
        self.maximum_active_checks = max(self.maximum_active_checks, self.active_checks)
        try:
            await asyncio.sleep(self.delay_seconds)
            if self.failure is not None:
                raise self.failure
            return self.ping_response
        finally:
            self.active_checks -= 1


def configure_started_app(probe_app, database, redis, deadline_seconds=0.05):
    probe_app.state.readiness = ReadinessState(
        engine_provider=lambda: database,
        redis_provider=lambda: redis,
        expected_revision="head",
        deadline_seconds=deadline_seconds,
    )
    probe_app.state.readiness.complete_startup()
    return probe_app


async def request_probe(app, path="/ready", cookies=None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path, cookies=cookies)


@pytest.mark.asyncio
async def test_process_serving_before_startup_is_live_but_not_ready(probe_app):
    async with AsyncClient(transport=ASGITransport(app=probe_app), base_url="http://test") as client:
        health_response = await client.get("/health")
        ready_response = await client.get("/ready")

    assert health_response.status_code == 200
    assert health_response.json() == {"status": "live"}
    assert ready_response.status_code == 503
    assert ready_response.json() == {"status": "not_ready"}


@pytest.mark.asyncio
async def test_operational_probes_ignore_stale_session_cookie(probe_app):
    async with AsyncClient(transport=ASGITransport(app=probe_app), base_url="http://test") as client:
        health_response = await client.get("/health", cookies={"session_id": "stale"})
        ready_response = await client.get("/ready", cookies={"session_id": "stale"})

    assert health_response.status_code == 200
    assert health_response.json() == {"status": "live"}
    assert ready_response.status_code == 503
    assert ready_response.json() == {"status": "not_ready"}


def test_runtime_schema_exposes_only_the_focused_probe_contract(probe_app):
    schema = probe_app.openapi()

    assert set(schema["paths"]["/health"]) == {"get"}
    assert set(schema["paths"]["/ready"]) == {"get"}
    assert set(schema["paths"]["/health"]["get"]["responses"]) == {"200"}
    assert {"200", "503"} <= set(schema["paths"]["/ready"]["get"]["responses"])
    assert schema["paths"]["/health"]["get"]["security"] == []
    assert schema["paths"]["/ready"]["get"]["security"] == []


@pytest.mark.asyncio
async def test_shutdown_started_is_not_ready_while_liveness_remains_live(probe_app):
    database = PlatformDatabaseBoundary()
    redis = RedisBoundary()
    app = configure_started_app(probe_app, database, redis)

    ready_response = await request_probe(app)
    app.state.readiness.begin_shutdown()
    shutdown_ready_response = await request_probe(app)
    shutdown_health_response = await request_probe(app, "/health")

    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ready"}
    assert shutdown_ready_response.status_code == 503
    assert shutdown_ready_response.json() == {"status": "not_ready"}
    assert shutdown_health_response.status_code == 200
    assert shutdown_health_response.json() == {"status": "live"}


@pytest.mark.asyncio
@pytest.mark.parametrize("dependency_name", ["database", "redis"])
async def test_unavailable_control_plane_dependency_recovers_without_restart(probe_app, dependency_name):
    database = PlatformDatabaseBoundary()
    redis = RedisBoundary()
    dependency = database if dependency_name == "database" else redis
    dependency.failure = OSError("private dependency detail")
    app = configure_started_app(probe_app, database, redis)

    unavailable_response = await request_probe(app)
    dependency.failure = None
    recovered_response = await request_probe(app)

    assert unavailable_response.status_code == 503
    assert unavailable_response.json() == {"status": "not_ready"}
    assert "private" not in unavailable_response.text
    assert recovered_response.status_code == 200
    assert recovered_response.json() == {"status": "ready"}


@pytest.mark.asyncio
@pytest.mark.parametrize("dependency_name", ["database", "redis"])
async def test_slow_control_plane_dependency_recovers_without_restart(probe_app, dependency_name):
    database = PlatformDatabaseBoundary()
    redis = RedisBoundary()
    dependency = database if dependency_name == "database" else redis
    dependency.delay_seconds = 0.2
    app = configure_started_app(probe_app, database, redis, deadline_seconds=0.02)

    slow_response = await request_probe(app)
    dependency.delay_seconds = 0
    recovered_response = await request_probe(app)

    assert slow_response.status_code == 503
    assert slow_response.json() == {"status": "not_ready"}
    assert recovered_response.status_code == 200
    assert recovered_response.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_malformed_redis_ping_recovers_without_restart(probe_app):
    database = PlatformDatabaseBoundary()
    redis = RedisBoundary()
    redis.ping_response = "PONG"
    app = configure_started_app(probe_app, database, redis)

    malformed_response = await request_probe(app)
    redis.ping_response = True
    recovered_response = await request_probe(app)

    assert malformed_response.status_code == 503
    assert malformed_response.json() == {"status": "not_ready"}
    assert recovered_response.status_code == 200
    assert recovered_response.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_alembic_drift_restores_without_restart(probe_app):
    database = PlatformDatabaseBoundary(revision="behind")
    redis = RedisBoundary()
    app = configure_started_app(probe_app, database, redis)

    drift_response = await request_probe(app)
    database.revision = "head"
    restored_response = await request_probe(app)

    assert drift_response.status_code == 503
    assert drift_response.json() == {"status": "not_ready"}
    assert restored_response.status_code == 200
    assert restored_response.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_simultaneous_dependency_failures_share_one_response_deadline(probe_app):
    database = PlatformDatabaseBoundary()
    redis = RedisBoundary()
    database.delay_seconds = 1
    redis.delay_seconds = 1
    app = configure_started_app(probe_app, database, redis, deadline_seconds=0.03)

    started_at = time.monotonic()
    response = await request_probe(app)
    elapsed_seconds = time.monotonic() - started_at

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert elapsed_seconds < 0.15
    assert database.active_checks == 0
    assert redis.active_checks == 0


@pytest.mark.asyncio
async def test_concurrent_probes_use_one_bounded_dependency_slot(probe_app):
    database = PlatformDatabaseBoundary()
    redis = RedisBoundary()
    database.delay_seconds = 0.01
    redis.delay_seconds = 0.01
    app = configure_started_app(probe_app, database, redis, deadline_seconds=0.2)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        responses = await asyncio.gather(*(client.get("/ready") for _ in range(8)))

    assert {response.status_code for response in responses} == {200}
    assert database.maximum_active_checks == 1
    assert redis.maximum_active_checks == 1


@pytest.mark.asyncio
async def test_ready_probe_ignores_cookie_and_feature_specific_dependencies(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "unavailable-provider")
    monkeypatch.setenv("SOURCE_DB_HOST", "source.invalid")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    get_settings.cache_clear()
    database = PlatformDatabaseBoundary()
    redis = RedisBoundary()
    app = configure_started_app(create_app(), database, redis)

    response = await request_probe(app, cookies={"session_id": "stale"})

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
