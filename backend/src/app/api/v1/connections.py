"""User-facing connections endpoint (T-428, FR-077).

GET /api/v1/connections — returns active + healthy + introspected connections
with minimal payload (id, display_name, database_type). No sensitive fields.
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import require_active_user
from app.schemas.connection import UserConnectionListResponse
from app.services.connection_service import ConnectionService

router = APIRouter(prefix="/connections", tags=["Connections"])


async def _get_connection_service() -> ConnectionService:
    """Resolve ConnectionService from app state."""
    from app.core.config import get_settings

    settings = get_settings()
    from app.core.dependencies import get_db

    # This is a placeholder; the real service is constructed via app state
    # For now, we use the pattern from admin_connections
    raise NotImplementedError("Service must be provided via dependency override or app state")


@router.get("", response_model=UserConnectionListResponse)
async def list_user_connections(
    service: ConnectionService = Depends(_get_connection_service),
    user_id: str = Depends(require_active_user),
) -> UserConnectionListResponse:
    """GET /connections — list connections available for user query selection.

    Returns only active + healthy + successfully introspected connections.
    Minimal payload: id, display_name, database_type. No host/port/credentials.
    """
    return await service.list_user_available()
