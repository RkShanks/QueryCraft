"""HTTP documentation exposure policy regressions for CHUNK-30."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.main import create_app

DOCUMENTATION_PATHS = ("/docs", "/redoc", "/docs/oauth2-redirect", "/openapi.json")


@pytest.fixture
def documentation_enabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("API_DOCUMENTATION_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.anyio
@pytest.mark.parametrize("path", DOCUMENTATION_PATHS)
async def test_secure_default_exposes_no_http_documentation(path: str):
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)

    assert response.status_code == 404


@pytest.mark.anyio
@pytest.mark.parametrize("path", DOCUMENTATION_PATHS)
async def test_explicit_enablement_exposes_development_documentation(documentation_enabled: None, path: str):
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)

    assert response.status_code == 200


def test_disabled_http_documentation_preserves_canonical_generation():
    app = create_app()
    application_operations = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute) and route.include_in_schema
        for method in route.methods
        if method not in {"HEAD", "OPTIONS"}
    }
    schema_operations = {
        (method.upper(), path)
        for path, path_contract in app.openapi()["paths"].items()
        for method in path_contract
        if method in {"delete", "get", "patch", "post", "put"}
    }

    assert schema_operations == application_operations
    assert len(schema_operations) == 65


def test_documentation_setting_rejects_ambiguous_values():
    with pytest.raises(ValidationError):
        Settings(API_DOCUMENTATION_ENABLED="sometimes")
