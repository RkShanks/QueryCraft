"""Phase 6 admin permission gate helpers."""

from app.api.dependencies.permissions import require_permission
from app.db.models.enums import Permission


def require_phase6_admin_permission(permission: Permission):
    """Use the shared audited permission gate for Phase 6 admin endpoints.

    The shared dependency provides the existing response contract and durable
    ``access.denied`` audit write:
      - No session (unauthenticated) → 401 error.unauthorized
      - Session present but missing required permission → 403 error.forbidden
    """
    return require_permission(permission)
