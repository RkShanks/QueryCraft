"""Explicit database-boundary fakes for permission-gated route tests."""

import uuid
from unittest.mock import AsyncMock, patch

from fastapi import Request

from app.api.dependencies.permissions import CurrentRole, get_current_role
from app.db.base import get_db


async def current_role_from_test_session(request: Request) -> CurrentRole | None:
    """Represent the current database role configured by a route test."""
    session = getattr(request.state, "session", None)
    if not isinstance(session, dict):
        return None
    role_id = session.get("role_id")
    permissions = session.get("permissions")
    if not isinstance(role_id, str) or not isinstance(permissions, list):
        return None
    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        return None
    role_name = session.get("role_name")
    if not isinstance(role_name, str):
        role_name = "Test role"
    return role_uuid, role_name, permissions


def use_test_session_current_role(app) -> None:
    """Configure a synthetic app to resolve its injected session as current."""
    app.dependency_overrides[get_current_role] = current_role_from_test_session
    app.dependency_overrides.setdefault(get_db, lambda: AsyncMock())


async def evaluate_permission_dependency(dependency, request: Request):
    """Call a permission dependency directly with explicit boundary fakes."""
    current_role = await current_role_from_test_session(request)
    with patch(
        "app.api.dependencies.permissions.AuditService.log",
        new_callable=AsyncMock,
    ):
        return await dependency(request, current_role, AsyncMock())
