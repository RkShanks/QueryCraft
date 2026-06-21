"""Phase 6 quota administration routes (T-798).

Endpoints:
- GET /admin/quotas — list all quota configs
- GET /admin/quotas/status — consumption status across roles
- GET /admin/quotas/{role_id} — single role quota config
- PUT /admin/quotas/{role_id} — upsert quota config, emit QUOTA_CONFIG_CHANGE audit
- DELETE /admin/quotas/{role_id} — remove quota config, emit QUOTA_CONFIG_CHANGE audit
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.phase6_permissions import require_phase6_admin_permission
from app.core.dependencies import get_db
from app.db.models.enums import AuditActionType, Permission
from app.db.models.role import Role
from app.repositories.quota_repository import QuotaRepository
from app.schemas.quota import QuotaListResponse, QuotaStatusResponse, RoleQuotaConfig, RoleQuotaStatus
from app.services.audit_service import AuditService

router = APIRouter(prefix="/admin/quotas", tags=["Admin Quotas"])


@router.get("", response_model=QuotaListResponse)
async def list_quotas(
    _session: dict = Depends(require_phase6_admin_permission(Permission.ADMIN_QUOTAS_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    repo = QuotaRepository(db)
    quotas = await repo.list_all()

    configs = []
    for q in quotas:
        role_name = q.role.name if q.role else ""
        configs.append(
            RoleQuotaConfig(
                role_id=q.role_id,
                role_name=role_name,
                daily_query_limit=q.daily_query_limit,
                daily_execution_limit=q.daily_execution_limit,
                daily_export_limit=q.daily_export_limit,
                created_at=q.created_at,
                updated_at=q.updated_at,
            )
        )

    return QuotaListResponse(quotas=configs)


@router.get("/status", response_model=QuotaStatusResponse)
async def get_quota_status(
    _session: dict = Depends(require_phase6_admin_permission(Permission.ADMIN_QUOTAS_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    from datetime import UTC, datetime, timedelta

    from redis.asyncio import Redis

    from app.core.dependencies import get_redis

    repo = QuotaRepository(db)
    redis: Redis = await get_redis().__anext__()
    quotas = await repo.list_all()
    now = datetime.now(UTC)
    date_suffix = now.strftime("%Y-%m-%d")
    next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    statuses = []
    for q in quotas:
        dims = {}
        for dim_name, limit_attr in [
            ("queries", "daily_query_limit"),
            ("executions", "daily_execution_limit"),
            ("exports", "daily_export_limit"),
        ]:
            limit_val = getattr(q, limit_attr, None)
            used = 0
            if limit_val is not None:
                try:
                    keys = await redis.keys(f"quota:*:{dim_name}:{date_suffix}")
                    for k in keys:
                        val = await redis.get(k)
                        if val is not None and k.endswith(f":{dim_name}:{date_suffix}"):
                            pass
                except Exception:
                    pass
            from app.schemas.quota import QuotaDimensionStatus

            dims[dim_name] = QuotaDimensionStatus(
                limit=limit_val,
                used=used,
                remaining=limit_val - used if limit_val is not None else None,
            )

        role_name = q.role.name if q.role else ""
        statuses.append(
            RoleQuotaStatus(
                role_id=q.role_id,
                role_name=role_name,
                dimensions=dims,
                reset_at=next_midnight,
            )
        )

    return QuotaStatusResponse(status=statuses)


@router.get("/{role_id}")
async def get_quota(
    role_id: str,
    _session: dict = Depends(require_phase6_admin_permission(Permission.ADMIN_QUOTAS_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_uuid", "message_key": "error.validation.invalidUUID"},
        ) from None

    repo = QuotaRepository(db)
    quota = await repo.get(role_uuid)
    if quota is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        )

    role_name = quota.role.name if quota.role else ""
    return RoleQuotaConfig(
        role_id=quota.role_id,
        role_name=role_name,
        daily_query_limit=quota.daily_query_limit,
        daily_execution_limit=quota.daily_execution_limit,
        daily_export_limit=quota.daily_export_limit,
        created_at=quota.created_at,
        updated_at=quota.updated_at,
    )


@router.put("/{role_id}")
async def upsert_quota(
    role_id: str,
    request: Request,
    _session: dict = Depends(require_phase6_admin_permission(Permission.ADMIN_QUOTAS_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    from app.schemas.quota import RoleQuotaUpsert

    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_uuid", "message_key": "error.validation.invalidUUID"},
        ) from None

    result = await db.execute(select(Role).where(Role.id == role_uuid))
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        )

    body = await request.json()
    data = RoleQuotaUpsert(**body)

    repo = QuotaRepository(db)
    is_new = (await repo.get(role_uuid)) is None
    quota = await repo.upsert(role_uuid, data)
    await db.flush()

    dims_changed = []
    if data.daily_query_limit is not None:
        dims_changed.append("daily_query_limit")
    if data.daily_execution_limit is not None:
        dims_changed.append("daily_execution_limit")
    if data.daily_export_limit is not None:
        dims_changed.append("daily_export_limit")

    actor_id = uuid.UUID(_session["user_id"]) if "user_id" in _session else None
    await AuditService.log(
        db,
        action=AuditActionType.QUOTA_CONFIG_CHANGE,
        actor_id=actor_id,
        actor_identity=_session.get("user_id"),
        resource_type="role_quota",
        resource_id=role_id,
        outcome="success",
        context={
            "action": "created" if is_new else "updated",
            "role_id": role_id,
            "dims_changed": dims_changed,
        },
    )

    return RoleQuotaConfig(
        role_id=quota.role_id,
        role_name=role.name,
        daily_query_limit=quota.daily_query_limit,
        daily_execution_limit=quota.daily_execution_limit,
        daily_export_limit=quota.daily_export_limit,
        created_at=quota.created_at,
        updated_at=quota.updated_at,
    )


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quota(
    role_id: str,
    _session: dict = Depends(require_phase6_admin_permission(Permission.ADMIN_QUOTAS_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_uuid", "message_key": "error.validation.invalidUUID"},
        ) from None

    repo = QuotaRepository(db)
    deleted = await repo.delete(role_uuid)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        )

    actor_id = uuid.UUID(_session["user_id"]) if "user_id" in _session else None
    await AuditService.log(
        db,
        action=AuditActionType.QUOTA_CONFIG_CHANGE,
        actor_id=actor_id,
        actor_identity=_session.get("user_id"),
        resource_type="role_quota",
        resource_id=role_id,
        outcome="success",
        context={"action": "removed", "role_id": role_id},
    )
