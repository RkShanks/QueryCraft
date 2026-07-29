"""Permission-gate denials must be durably audited without leaking request data."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI, Request
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.dependencies.permissions import get_current_role, require_permission
from app.api.v1.phase6_permissions import require_phase6_admin_permission
from app.db.base import get_db
from app.db.models.enums import AuditActionType, Permission
from tests.unit.permission_test_helpers import current_role_from_test_session


def _protected_app(session: dict | None, db, permission_dependency=None) -> FastAPI:
    class SessionInjectionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.session = session
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(SessionInjectionMiddleware)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_role] = current_role_from_test_session
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
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "username": "restricted-user",
                "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
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
    app = _protected_app(session, db, permission_dependency)

    with patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as audit_log:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/protected")

    assert response.status_code == expected_status
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
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "username": "authorized-user",
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
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
