"""Permission dependency — FastAPI dependency for role-based access control.

Provides ``require_permission(*perms)`` which checks the current session's
permission list against the required set. Denials are durably recorded as
``access.denied`` before returning a sanitized 401 or 403 response.
"""

from typing import Never

from fastapi import HTTPException, Request, status

from app.db.base import get_async_session_factory
from app.db.models.enums import AuditActionType, Permission
from app.services.audit_service import AuditService


async def _audit_access_denied(
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

    session_factory = get_async_session_factory()
    async with session_factory() as db:
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
    """Return a FastAPI dependency that checks session permissions.

    Args:
        perms: One or more Permission enum values required for access.

    Returns:
        An async callable suitable for ``Depends()`` that validates the
        request's session data contains at least one of the required
        permissions.

    Raises:
        HTTPException 401: No session data present (unauthenticated).
        HTTPException 403: Session exists but lacks required permission(s).

    Side Effects:
        Commits a sanitized ``access.denied`` audit entry before raising a
        denial response. Audit failures propagate so authorization remains
        fail-closed.
    """
    required = {str(p) for p in perms}

    async def _checker(request: Request) -> dict:
        session = getattr(request.state, "session", None)

        async def deny(status_code: int, error: str, reason: str) -> Never:
            await _audit_access_denied(
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
        # Unmapped user denial: role_id must be a non-empty string (FR-126, SC-048)
        role_id = session.get("role_id")
        if not isinstance(role_id, str) or not role_id.strip():
            await deny(status.HTTP_403_FORBIDDEN, "forbidden", "unmapped_role")
        user_perms = set(session.get("permissions", []))
        if not (user_perms & required):
            await deny(status.HTTP_403_FORBIDDEN, "forbidden", "missing_permission")
        return session

    return _checker
