"""Permission dependency — FastAPI dependency for role-based access control.

Provides ``require_permission(*perms)`` which checks the user's current
database role against the required set. Denials are durably recorded as
``access.denied`` before returning a sanitized 401 or 403 response.
"""

import uuid
from typing import Never

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models.enums import AuditActionType, Permission
from app.db.models.role import Role
from app.db.models.user import User
from app.services.audit_service import AuditService

CurrentRole = tuple[uuid.UUID, str, list[str]]


async def get_current_role(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> CurrentRole | None:
    """Resolve the caller's current database role from the session user ID."""
    session = getattr(request.state, "session", None)
    if not isinstance(session, dict):
        return None
    user_id = session.get("user_id")
    try:
        user_uuid = uuid.UUID(user_id)
    except (TypeError, ValueError):
        return None

    row = (
        await db.execute(
            select(Role.id, Role.name, Role.permissions).join(User, User.role_id == Role.id).where(User.id == user_uuid)
        )
    ).one_or_none()
    if row is None:
        return None
    return row.id, row.name, list(row.permissions or [])


async def _audit_access_denied(
    db,
    session: dict | None,
    *,
    reason: str,
    request_method: str,
    required_permissions: set[str],
) -> None:
    actor_identity = None
    if isinstance(session, dict):
        username = session.get("username")
        if isinstance(username, str) and username.strip():
            actor_identity = username

    await AuditService.log(
        db,
        action=AuditActionType.ACCESS_DENIED,
        actor_identity=actor_identity,
        resource_type="authorization",
        outcome="denied",
        context={
            "reason": reason,
            "request_method": request_method,
            "required_permissions": sorted(required_permissions),
        },
    )
    await db.commit()


def require_permission(*perms: Permission):
    """Return a FastAPI dependency that checks current database permissions.

    Args:
        perms: One or more Permission enum values required for access.

    Returns:
        An async callable suitable for ``Depends()`` that validates the
        caller's current database role contains at least one required
        permission. Session role claims are refreshed only after lookup.

    Raises:
        HTTPException 401: No session data present (unauthenticated).
        HTTPException 403: Session exists but lacks required permission(s).

    Side Effects:
        Commits a sanitized ``access.denied`` audit entry before raising a
        denial response. Audit failures propagate so authorization remains
        fail-closed.
    """
    required = {str(p) for p in perms}

    async def _checker(
        request: Request,
        current_role: CurrentRole | None = Depends(get_current_role),  # noqa: B008
        db: AsyncSession = Depends(get_db),  # noqa: B008
    ) -> dict:
        session = getattr(request.state, "session", None)

        async def deny(status_code: int, error: str, reason: str) -> Never:
            await _audit_access_denied(
                db,
                session,
                reason=reason,
                request_method=request.method,
                required_permissions=required,
            )
            raise HTTPException(
                status_code=status_code,
                detail={"error": error, "message_key": f"error.{error}"},
            )

        if session is None:
            await deny(status.HTTP_401_UNAUTHORIZED, "unauthorized", "unauthenticated")
        if current_role is None:
            await deny(status.HTTP_403_FORBIDDEN, "forbidden", "unmapped_role")
        role_id, role_name, permissions = current_role
        session.update(
            role_id=str(role_id),
            role_name=role_name,
            permissions=permissions,
        )
        user_perms = set(permissions)
        if not (user_perms & required):
            await deny(status.HTTP_403_FORBIDDEN, "forbidden", "missing_permission")
        return session

    return _checker
