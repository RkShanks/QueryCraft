"""Admin connection management endpoints (T-412, T-413, T-414).

FR-059, FR-060, FR-061, FR-063, FR-064, FR-089:
CRUD, lifecycle (disable/enable), health test, hard-delete guard.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.permissions import require_permission
from app.core.config import get_settings
from app.core.dependencies import get_db
from app.db.models.enums import Permission
from app.repositories.connection_repository import ConnectionRepository
from app.schemas.connection import (
    ConnectionCreate,
    ConnectionResponse,
    ConnectionTestResult,
    ConnectionUpdate,
)
from app.services.connection_service import (
    ConnectionNotFoundError,
    ConnectionReferencedError,
    ConnectionService,
)

router = APIRouter(prefix="/admin/connections", tags=["Admin Connections"])


def _get_connection_service(
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ConnectionService:
    """Create a ConnectionService with repository and credential key."""
    settings = get_settings()
    repo = ConnectionRepository(db)
    return ConnectionService(repo, settings.DB_CREDENTIAL_KEY, get_db_session=lambda: db)


@router.get("", response_model=list[ConnectionResponse])
async def list_connections(
    _session: dict = Depends(require_permission(Permission.ADMIN_CONNECTIONS_MANAGE)),  # noqa: B008
    service: ConnectionService = Depends(_get_connection_service),  # noqa: B008
):
    """GET /admin/connections — list all source database connections.

    Requires ``admin.connections.manage`` permission.
    """
    try:
        connections = await service.list_all()
        return connections
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message_key": "error.internal"},
        ) from e


@router.post("", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(
    req: ConnectionCreate,
    _session: dict = Depends(require_permission(Permission.ADMIN_CONNECTIONS_MANAGE)),  # noqa: B008
    service: ConnectionService = Depends(_get_connection_service),  # noqa: B008
):
    """POST /admin/connections — create a new source database connection.

    Requires ``admin.connections.manage`` permission.
    """
    try:
        return await service.create(req)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message_key": "error.internal"},
        ) from e


@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection(
    connection_id: uuid.UUID,
    _session: dict = Depends(require_permission(Permission.ADMIN_CONNECTIONS_MANAGE)),  # noqa: B008
    service: ConnectionService = Depends(_get_connection_service),  # noqa: B008
):
    """GET /admin/connections/{id} — get a connection by ID.

    Requires ``admin.connections.manage`` permission.
    """
    try:
        return await service.get_by_id(connection_id)
    except ConnectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "connection_not_found", "message_key": "error.connection_not_found"},
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message_key": "error.internal"},
        ) from e


@router.put("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: uuid.UUID,
    req: ConnectionUpdate,
    _session: dict = Depends(require_permission(Permission.ADMIN_CONNECTIONS_MANAGE)),  # noqa: B008
    service: ConnectionService = Depends(_get_connection_service),  # noqa: B008
):
    """PUT /admin/connections/{id} — update an existing connection.

    Requires ``admin.connections.manage`` permission.
    """
    try:
        return await service.update(connection_id, req)
    except ConnectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "connection_not_found", "message_key": "error.connection_not_found"},
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message_key": "error.internal"},
        ) from e


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: uuid.UUID,
    _session: dict = Depends(require_permission(Permission.ADMIN_CONNECTIONS_MANAGE)),  # noqa: B008
    service: ConnectionService = Depends(_get_connection_service),  # noqa: B008
):
    """DELETE /admin/connections/{id} — hard-delete a connection (blocked if referenced).

    Requires ``admin.connections.manage`` permission.
    """
    try:
        await service.hard_delete(connection_id)
    except ConnectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "connection_not_found", "message_key": "error.connection_not_found"},
        ) from None
    except ConnectionReferencedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "connection_referenced", "message_key": "error.connection_referenced_delete_blocked"},
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message_key": "error.internal"},
        ) from e


@router.post("/{connection_id}/disable", response_model=ConnectionResponse)
async def disable_connection(
    connection_id: uuid.UUID,
    _session: dict = Depends(require_permission(Permission.ADMIN_CONNECTIONS_MANAGE)),  # noqa: B008
    service: ConnectionService = Depends(_get_connection_service),  # noqa: B008
):
    """POST /admin/connections/{id}/disable — disable an active connection.

    Requires ``admin.connections.manage`` permission.
    """
    try:
        return await service.disable(connection_id)
    except ConnectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "connection_not_found", "message_key": "error.connection_not_found"},
        ) from None
    except Exception as e:
        if "already_disabled" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "already_disabled", "message_key": "error.connection_already_disabled"},
            ) from None
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message_key": "error.internal"},
        ) from e


@router.post("/{connection_id}/enable", response_model=ConnectionResponse)
async def enable_connection(
    connection_id: uuid.UUID,
    _session: dict = Depends(require_permission(Permission.ADMIN_CONNECTIONS_MANAGE)),  # noqa: B008
    service: ConnectionService = Depends(_get_connection_service),  # noqa: B008
):
    """POST /admin/connections/{id}/enable — re-enable a disabled connection.

    Requires ``admin.connections.manage`` permission.
    """
    try:
        return await service.enable(connection_id)
    except ConnectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "connection_not_found", "message_key": "error.connection_not_found"},
        ) from None
    except Exception as e:
        if "already_active" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "already_active", "message_key": "error.connection_already_active"},
            ) from None
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message_key": "error.internal"},
        ) from e


@router.post("/{connection_id}/test", response_model=ConnectionTestResult)
async def test_connection(
    connection_id: uuid.UUID,
    _session: dict = Depends(require_permission(Permission.ADMIN_CONNECTIONS_MANAGE)),  # noqa: B008
    service: ConnectionService = Depends(_get_connection_service),  # noqa: B008
):
    """POST /admin/connections/{id}/test — test a connection's health.

    Requires ``admin.connections.manage`` permission.
    """
    try:
        return await service.test_connection(connection_id)
    except ConnectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "connection_not_found", "message_key": "error.connection_not_found"},
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message_key": "error.internal"},
        ) from e


@router.post("/{connection_id}/refresh-schema")
async def refresh_schema(
    connection_id: uuid.UUID,
    _session: dict = Depends(require_permission(Permission.ADMIN_CONNECTIONS_MANAGE)),  # noqa: B008
    service: ConnectionService = Depends(_get_connection_service),  # noqa: B008
):
    """POST /admin/connections/{id}/refresh-schema — trigger schema introspection.

    Requires ``admin.connections.manage`` permission.
    """
    try:
        result = await service.refresh_schema(connection_id)
        return result
    except ConnectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "connection_not_found", "message_key": "error.connection_not_found"},
        ) from None
    except Exception as e:
        if hasattr(e, "message_key") and e.message_key == "error.introspection_failed":  # type: ignore[attr-defined]
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": "introspection_failed", "message_key": "error.introspection_failed"},
            ) from e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message_key": "error.internal"},
        ) from e


@router.get("/{connection_id}/schema")
async def get_schema(
    connection_id: uuid.UUID,
    _session: dict = Depends(require_permission(Permission.ADMIN_CONNECTIONS_MANAGE)),  # noqa: B008
    service: ConnectionService = Depends(_get_connection_service),  # noqa: B008
):
    """GET /admin/connections/{id}/schema — get introspected schema summary.

    Requires ``admin.connections.manage`` permission.
    """
    try:
        result = await service.get_schema_summary(connection_id)
        return result
    except ConnectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "connection_not_found", "message_key": "error.connection_not_found"},
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message_key": "error.internal"},
        ) from e
