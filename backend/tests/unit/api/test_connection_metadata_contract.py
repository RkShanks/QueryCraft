"""XP-012 regression coverage for admin connection response metadata."""

import json
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.dependencies.permissions import get_current_role
from app.api.v1.admin_connections import _get_connection_service, router
from app.core.dependencies import get_db
from app.services.connection_service import ConnectionService
from tests.unit.permission_test_helpers import use_test_session_current_role

_FORBIDDEN_RESPONSE_FIELDS = {
    "host",
    "username",
    "password",
    "encrypted_password",
    "database_url",
}


def _connection_payload(runtime_sensitive_values: list[str]) -> dict:
    now = datetime.now(UTC).isoformat()
    return {
        "id": str(uuid4()),
        "display_name": "Runtime connection",
        "database_type": "postgresql",
        "host": runtime_sensitive_values[0],
        "port": 5432,
        "database_name": "analytics",
        "username": runtime_sensitive_values[1],
        "password": runtime_sensitive_values[2],
        "encrypted_password": runtime_sensitive_values[3],
        "database_url": runtime_sensitive_values[4],
        "ssl_mode": "require",
        "lifecycle_state": "active",
        "health_status": "healthy",
        "last_health_check_at": None,
        "health_error_category": None,
        "schema_introspection_status": "success",
        "schema_last_refreshed_at": None,
        "created_at": now,
        "updated_at": now,
    }


def _connection_app(service: ConnectionService) -> FastAPI:
    role_id = str(uuid4())
    session = {
        "role_id": role_id,
        "permissions": ["admin.connections.manage"],
    }

    class SessionInjectionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.session = dict(session)
            return await call_next(request)

    app = FastAPI()
    use_test_session_current_role(app)
    app.add_middleware(SessionInjectionMiddleware)
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[_get_connection_service] = lambda: service
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path_template", "service_method", "expected_status"),
    [
        ("GET", "/api/v1/admin/connections", "list_all", 200),
        ("POST", "/api/v1/admin/connections", "create", 201),
        ("GET", "/api/v1/admin/connections/{connection_id}", "get_by_id", 200),
        ("PUT", "/api/v1/admin/connections/{connection_id}", "update", 200),
        ("POST", "/api/v1/admin/connections/{connection_id}/disable", "disable", 200),
        ("POST", "/api/v1/admin/connections/{connection_id}/enable", "enable", 200),
    ],
)
async def test_admin_connection_responses_omit_metadata_and_prevent_storage(
    method,
    path_template,
    service_method,
    expected_status,
):
    runtime_sensitive_values = [uuid4().hex for _ in range(8)]
    response_payload = _connection_payload(runtime_sensitive_values)
    service = MagicMock(spec=ConnectionService)
    service_response = [response_payload] if service_method == "list_all" else response_payload
    setattr(service, service_method, AsyncMock(return_value=service_response))
    app = _connection_app(service)
    path = path_template.format(connection_id=uuid4())
    request_body = None
    if service_method == "create":
        request_body = {
            "display_name": "Runtime connection",
            "database_type": "postgresql",
            "host": runtime_sensitive_values[5],
            "port": 5432,
            "database_name": "analytics",
            "username": runtime_sensitive_values[6],
            "password": runtime_sensitive_values[7],
        }
    elif service_method == "update":
        request_body = {}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(method, path, json=request_body)

    assert response.status_code == expected_status
    response_body = response.json()
    connection_body = response_body[0] if isinstance(response_body, list) else response_body
    leaked_keys = set(connection_body) & _FORBIDDEN_RESPONSE_FIELDS
    leaked_values = any(probe in response.text for probe in runtime_sensitive_values)
    assert leaked_keys == set()
    assert leaked_values is False
    assert response.headers.get("cache-control") == "no-store"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path_template", "invalid_field"),
    [
        ("POST", "/api/v1/admin/connections", "password"),
        ("PUT", "/api/v1/admin/connections/{connection_id}", "username"),
    ],
)
async def test_connection_validation_errors_are_sanitized(
    method,
    path_template,
    invalid_field,
    redis_client,
):
    runtime_sensitive_value = uuid4().hex
    role_id = uuid4()
    session_id = uuid4().hex
    await redis_client.set(
        f"session:{session_id}",
        json.dumps(
            {
                "role_id": str(role_id),
                "permissions": ["admin.connections.manage"],
                "last_activity": time.time(),
            }
        ),
    )

    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_current_role] = lambda: (
        role_id,
        "Runtime role",
        ["admin.connections.manage"],
    )
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[_get_connection_service] = lambda: MagicMock(spec=ConnectionService)
    path = path_template.format(connection_id=uuid4())
    request_body = {
        "display_name": "Runtime connection",
        "database_type": "postgresql",
        "host": uuid4().hex,
        "port": 5432,
        "database_name": "analytics",
        "username": uuid4().hex,
        "password": uuid4().hex,
    }
    request_body = request_body if method == "POST" else {}
    request_body[invalid_field] = f"{runtime_sensitive_value}\x00"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.cookies.set("session_id", session_id)
        response = await client.request(
            method,
            path,
            json=request_body,
            headers={"origin": "http://test"},
        )

    response_keys = set(response.json())
    leaked_value = runtime_sensitive_value in response.text
    assert response.status_code == 422
    assert response_keys == {"error", "message_key", "details"}
    assert leaked_value is False
