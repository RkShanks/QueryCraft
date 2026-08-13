"""Operational liveness and readiness HTTP contract regressions."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def probe_app(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    get_settings.cache_clear()
    return create_app()


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
