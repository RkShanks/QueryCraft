"""Role admin endpoints (T-674).

Protected by ``admin.roles.manage`` permission.
Endpoints:
- GET /admin/roles
- POST /admin/roles
- GET /admin/roles/{id}
- PUT /admin/roles/{id}
- DELETE /admin/roles/{id}
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.permissions import require_permission
from app.core.dependencies import get_db
from app.core.exceptions import BuiltinProtectedError
from app.db.models.enums import Permission
from app.db.models.role import Role
from app.db.models.role_connection_policy import RoleConnectionPolicy
from app.db.models.sso_group_mapping import SsoGroupMapping
from app.repositories.role_repository import RoleRepository
from app.schemas.roles import RoleCreate, RoleUpdate
from app.services.role_service import RoleService

router = APIRouter(prefix="/admin/roles", tags=["Admin Roles"])


def _role_to_list_response(role: Role, group_mappings: list, connection_policy_count: int) -> dict:
    return {
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
        "priority": role.priority,
        "permissions": role.permissions or [],
        "is_builtin": getattr(role, "is_builtin", False),
        "group_mappings": group_mappings,
        "connection_policy_count": connection_policy_count,
        "created_at": role.created_at.isoformat() if role.created_at else None,
        "updated_at": role.updated_at.isoformat() if role.updated_at else None,
    }


def _role_to_detail_response(role: Role, group_mappings: list, connection_policies: list) -> dict:
    return {
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
        "priority": role.priority,
        "permissions": role.permissions or [],
        "is_builtin": getattr(role, "is_builtin", False),
        "group_mappings": group_mappings,
        "connection_policies": connection_policies,
        "created_at": role.created_at.isoformat() if role.created_at else None,
        "updated_at": role.updated_at.isoformat() if role.updated_at else None,
    }


def _validate_permissions(permissions: list[str] | None) -> None:
    """Validate permission values against the fixed allowed set."""
    allowed = {p.value for p in Permission}
    if permissions is None:
        return
    invalid = [p for p in permissions if p not in allowed]
    if invalid:
        raise ValueError(f"Invalid permissions: {', '.join(invalid)}")


@router.get("")
async def list_roles(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """GET /admin/roles — list all roles."""
    await require_permission(Permission.ADMIN_ROLES_MANAGE)(request)

    try:
        repo = RoleRepository(db)
        service = RoleService(repo)
        roles = await service.list_roles()

        # Fetch all group mappings
        gm_result = await db.execute(select(SsoGroupMapping))
        gm_rows = gm_result.scalars().all()
        gm_by_role: dict = {}
        for gm in gm_rows:
            gm_by_role.setdefault(str(gm.role_id), []).append(
                {
                    "id": str(gm.id),
                    "sso_group_value": gm.sso_group_value,
                }
            )

        # Fetch connection policy counts
        cp_result = await db.execute(
            select(RoleConnectionPolicy.role_id, func.count(RoleConnectionPolicy.id)).group_by(
                RoleConnectionPolicy.role_id
            )
        )
        cp_counts = {str(row[0]): row[1] for row in cp_result.all()}

        return {
            "roles": [
                _role_to_list_response(
                    role,
                    gm_by_role.get(str(role.id), []),
                    cp_counts.get(str(role.id), 0),
                )
                for role in roles
            ]
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_role(
    request: Request,
    body: RoleCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """POST /admin/roles — create a new role."""
    await require_permission(Permission.ADMIN_ROLES_MANAGE)(request)

    try:
        _validate_permissions(body.permissions)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "message_key": "error.validation.invalidPermissions"},
        ) from None

    try:
        repo = RoleRepository(db)
        service = RoleService(repo)

        session = getattr(request.state, "session", {}) or {}
        role = await service.create_role(
            name=body.name,
            description=body.description,
            priority=body.priority,
            permissions=body.permissions,
            actor_identity=session.get("username"),
            db_session=db,
        )

        await db.commit()
        await db.refresh(role)

        return _role_to_detail_response(role, [], [])
    except BuiltinProtectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message_key": exc.message_key},
        ) from None
    except ValueError as exc:
        msg = str(exc)
        if "duplicate_name" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "conflict", "message_key": "error.conflict.duplicateName"},
            ) from None
        if "duplicate_priority" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "conflict", "message_key": "error.conflict.duplicatePriority"},
            ) from None
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        ) from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None


@router.get("/{role_id}")
async def get_role(
    request: Request,
    role_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """GET /admin/roles/{id} — get role detail."""
    await require_permission(Permission.ADMIN_ROLES_MANAGE)(request)

    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        ) from None

    try:
        repo = RoleRepository(db)
        service = RoleService(repo)
        role = await service.get_role(role_uuid)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message_key": "error.notFound"},
            )

        gm_result = await db.execute(select(SsoGroupMapping).where(SsoGroupMapping.role_id == role_id))
        gm_rows = gm_result.scalars().all()
        group_mappings = [{"id": str(gm.id), "sso_group_value": gm.sso_group_value} for gm in gm_rows]

        cp_result = await db.execute(select(RoleConnectionPolicy).where(RoleConnectionPolicy.role_id == role_id))
        cp_rows = cp_result.scalars().all()
        connection_policies = []
        for cp in cp_rows:
            connection_policies.append(
                {
                    "id": str(cp.id),
                    "connection_id": str(cp.connection_id),
                    "allowed_tables": cp.allowed_tables or [],
                    "row_filters": cp.row_filters or [],
                    "column_masks": cp.column_masks or [],
                }
            )

        return _role_to_detail_response(role, group_mappings, connection_policies)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None


@router.put("/{role_id}")
async def update_role(
    request: Request,
    role_id: str,
    body: RoleUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """PUT /admin/roles/{id} — update a role."""
    await require_permission(Permission.ADMIN_ROLES_MANAGE)(request)

    try:
        _validate_permissions(body.permissions)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "message_key": "error.validation.invalidPermissions"},
        ) from None

    fields = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.description is not None:
        fields["description"] = body.description
    if body.priority is not None:
        fields["priority"] = body.priority
    if body.permissions is not None:
        fields["permissions"] = body.permissions

    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        ) from None

    try:
        repo = RoleRepository(db)
        service = RoleService(repo)

        session = getattr(request.state, "session", {}) or {}
        role = await service.update_role(
            role_id=role_uuid,
            fields=fields,
            actor_identity=session.get("username"),
            db_session=db,
        )

        await db.commit()
        await db.refresh(role)

        return _role_to_detail_response(role, [], [])
    except BuiltinProtectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message_key": exc.message_key},
        ) from None
    except ValueError as exc:
        msg = str(exc)
        if "duplicate_name" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "conflict", "message_key": "error.conflict.duplicateName"},
            ) from None
        if "duplicate_priority" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "conflict", "message_key": "error.conflict.duplicatePriority"},
            ) from None
        if "not_found" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message_key": "error.notFound"},
            ) from None
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "message_key": "error.validation.generic"},
        ) from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    request: Request,
    role_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """DELETE /admin/roles/{id} — remove a role."""
    await require_permission(Permission.ADMIN_ROLES_MANAGE)(request)

    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        ) from None

    try:
        repo = RoleRepository(db)
        service = RoleService(repo)

        session = getattr(request.state, "session", {}) or {}
        await service.delete_role(
            role_id=role_uuid,
            actor_identity=session.get("username"),
            db_session=db,
        )

        await db.commit()
        return None
    except BuiltinProtectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message_key": exc.message_key},
        ) from None
    except ValueError as exc:
        if "not_found" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message_key": "error.notFound"},
            ) from None
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "message_key": "error.validation.generic"},
        ) from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None
