"""Permission dependency — FastAPI dependency for role-based access control.

Provides ``require_permission(*perms)`` which checks the current session's
permission list against the required set. Returns 403 with sanitized
``error.forbidden`` on failure, 401 if no session exists.
"""

from fastapi import HTTPException, Request, status

from app.db.models.enums import Permission


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
    """
    required = {str(p) for p in perms}

    async def _checker(request: Request) -> dict:
        session = getattr(request.state, "session", None)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthorized", "message_key": "error.unauthorized"},
            )
        # Unmapped user denial: role_id must be a non-empty string (FR-126, SC-048)
        role_id = session.get("role_id")
        if not isinstance(role_id, str) or not role_id.strip():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "forbidden", "message_key": "error.forbidden"},
            )
        user_perms = set(session.get("permissions", []))
        if not (user_perms & required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "forbidden", "message_key": "error.forbidden"},
            )
        return session

    return _checker
