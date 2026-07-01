"""Phase 6 admin permission gate helpers."""

from fastapi import HTTPException, Request, status

from app.db.models.enums import Permission


def require_phase6_admin_permission(permission: Permission):
    """Return 401 for unauthenticated requests, 403 for insufficient Phase 6 admin access.

    Mirrors the contract of ``require_permission`` in
    ``app.api.dependencies.permissions``:
      - No session (unauthenticated) → 401 error.unauthorized
      - Session present but missing required permission → 403 error.forbidden
    """
    required = str(permission)

    async def _checker(request: Request) -> dict:
        session = getattr(request.state, "session", None)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthorized", "message_key": "error.unauthorized"},
            )
        role_id = session.get("role_id")
        permissions = set(session.get("permissions", []))
        if not isinstance(role_id, str) or not role_id.strip() or required not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "forbidden", "message_key": "error.forbidden"},
            )
        return session

    return _checker
