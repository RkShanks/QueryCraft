"""Permission-gate denials must be durably audited without leaking request data."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI, Request
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.dependencies.permissions import require_permission
from app.db.base import get_db
from app.db.models.enums import AuditActionType, Permission


def _protected_app(session: dict | None, db: AsyncMock) -> FastAPI:
    class SessionInjectionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.session = session
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(SessionInjectionMiddleware)

    async def override_db():
        return db

    app.dependency_overrides[get_db] = override_db

    @app.get("/protected")
    async def protected(
        _session: dict = Depends(require_permission(Permission.ADMIN_AUDIT_VERIFY)),  # noqa: B008
    ):
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_authenticated_permission_denial_is_durably_audited():
    db = AsyncMock()
    app = _protected_app(
        {
            "username": "restricted-user",
            "role_id": "restricted-role",
            "permissions": [Permission.QUERY_SUBMIT.value],
        },
        db,
    )

    with patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as audit_log:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/protected")

    assert response.status_code == 403
    audit_log.assert_awaited_once_with(
        db,
        action=AuditActionType.ACCESS_DENIED,
        actor_identity="restricted-user",
        resource_type="authorization",
        outcome="denied",
        context={
            "reason": "missing_permission",
            "request_method": "GET",
            "required_permissions": [Permission.ADMIN_AUDIT_VERIFY.value],
        },
    )
    db.commit.assert_awaited_once_with()
    assert "admin.audit.verify" not in response.text
    assert "restricted-user" not in response.text


@pytest.mark.asyncio
async def test_unauthenticated_permission_denial_is_durably_audited():
    db = AsyncMock()
    app = _protected_app(None, db)

    with patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as audit_log:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/protected")

    assert response.status_code == 401
    audit_log.assert_awaited_once_with(
        db,
        action=AuditActionType.ACCESS_DENIED,
        actor_identity=None,
        resource_type="authorization",
        outcome="denied",
        context={
            "reason": "unauthenticated",
            "request_method": "GET",
            "required_permissions": [Permission.ADMIN_AUDIT_VERIFY.value],
        },
    )
    db.commit.assert_awaited_once_with()
    assert "admin.audit.verify" not in response.text


@pytest.mark.asyncio
async def test_authorized_request_does_not_emit_access_denied():
    db = AsyncMock()
    app = _protected_app(
        {
            "username": "authorized-user",
            "role_id": "authorized-role",
            "permissions": [Permission.ADMIN_AUDIT_VERIFY.value],
        },
        db,
    )

    with patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as audit_log:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/protected")

    assert response.status_code == 200
    audit_log.assert_not_awaited()
    db.commit.assert_not_awaited()
