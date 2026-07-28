"""Permission-gate denials must be durably audited without leaking request data."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI, Request
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.dependencies.permissions import require_permission
from app.api.v1.phase6_permissions import require_phase6_admin_permission
from app.db.models.enums import AuditActionType, Permission


@asynccontextmanager
async def _db_context(db):
    yield db


def _protected_app(session: dict | None, permission_dependency=None) -> FastAPI:
    class SessionInjectionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.session = session
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(SessionInjectionMiddleware)
    permission_dependency = permission_dependency or require_permission(Permission.ADMIN_AUDIT_VERIFY)

    @app.get("/protected")
    async def protected(
        _session: dict = Depends(permission_dependency),  # noqa: B008
    ):
        return {"ok": True}

    return app


@pytest.mark.parametrize(
    ("session", "expected_status", "expected_actor", "expected_reason"),
    [
        (
            {
                "username": "restricted-user",
                "role_id": "restricted-role",
                "permissions": [Permission.QUERY_SUBMIT.value],
            },
            403,
            "restricted-user",
            "missing_permission",
        ),
        (None, 401, None, "unauthenticated"),
    ],
)
@pytest.mark.parametrize(
    "permission_dependency",
    [
        pytest.param(
            require_permission(Permission.ADMIN_AUDIT_VERIFY),
            id="phase5-gate",
        ),
        pytest.param(
            require_phase6_admin_permission(Permission.ADMIN_AUDIT_VERIFY),
            id="phase6-gate",
        ),
    ],
)
@pytest.mark.asyncio
async def test_permission_denial_is_durably_audited(
    session,
    expected_status,
    expected_actor,
    expected_reason,
    permission_dependency,
):
    db = AsyncMock()
    app = _protected_app(session, permission_dependency)

    def session_factory():
        return _db_context(db)

    with (
        patch(
            "app.api.dependencies.permissions.get_async_session_factory",
            return_value=session_factory,
        ) as get_session_factory,
        patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as audit_log,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/protected")

    assert response.status_code == expected_status
    get_session_factory.assert_called_once_with()
    audit_log.assert_awaited_once_with(
        db,
        action=AuditActionType.ACCESS_DENIED,
        actor_identity=expected_actor,
        resource_type="authorization",
        outcome="denied",
        context={
            "reason": expected_reason,
            "request_method": "GET",
            "required_permissions": [Permission.ADMIN_AUDIT_VERIFY.value],
        },
    )
    db.commit.assert_awaited_once_with()
    assert "admin.audit.verify" not in response.text
    assert "restricted-user" not in response.text


@pytest.mark.asyncio
async def test_authorized_request_does_not_emit_access_denied():
    db = AsyncMock()
    app = _protected_app(
        {
            "username": "authorized-user",
            "role_id": "authorized-role",
            "permissions": [Permission.ADMIN_AUDIT_VERIFY.value],
        }
    )

    with (
        patch("app.api.dependencies.permissions.get_async_session_factory") as get_session_factory,
        patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as audit_log,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/protected")

    assert response.status_code == 200
    get_session_factory.assert_not_called()
    audit_log.assert_not_awaited()
    db.commit.assert_not_awaited()
