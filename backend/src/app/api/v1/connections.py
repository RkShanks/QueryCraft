"""User-facing connections endpoint (T-428, FR-077).

GET /api/v1/connections — returns active + healthy + introspected connections
with minimal payload (id, display_name, database_type). No sensitive fields.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_db, require_active_user
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.connection import UserConnectionListResponse
from app.services.connection_service import ConnectionService

router = APIRouter(prefix="/connections", tags=["Connections"])


def _get_connection_service(
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ConnectionService:
    """Create a ConnectionService with repository and credential key."""
    settings = get_settings()
    repo = ConnectionRepository(db)
    return ConnectionService(repo, settings.DB_CREDENTIAL_KEY, get_db_session=lambda: db)


@router.get("", response_model=UserConnectionListResponse)
async def list_user_connections(
    service: ConnectionService = Depends(_get_connection_service),  # noqa: B008
    user_id: str = Depends(require_active_user),  # noqa: B008,
) -> UserConnectionListResponse:
    """GET /connections — list connections available for user query selection.

    Returns only active + healthy + successfully introspected connections.
    Minimal payload: id, display_name, database_type. No host/port/credentials.
    """
    return await service.list_user_available()
