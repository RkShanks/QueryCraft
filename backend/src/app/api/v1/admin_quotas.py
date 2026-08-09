"""Phase 6 quota administration routes (T-798).

Endpoints:
- GET /admin/quotas — list all quota configs
- GET /admin/quotas/status — consumption status across roles
- GET /admin/quotas/{role_id} — single role quota config
- PUT /admin/quotas/{role_id} — upsert quota config, emit QUOTA_CONFIG_CHANGE audit
- DELETE /admin/quotas/{role_id} — remove quota config, emit QUOTA_CONFIG_CHANGE audit
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.validation import validate_body
from app.api.v1.phase6_permissions import require_phase6_admin_permission
from app.core.dependencies import get_db, get_redis
from app.core.exceptions import QuotaUnavailableError
from app.db.models.enums import AuditActionType, Permission
from app.db.models.role import Role
from app.db.models.role_quota import RoleQuota
from app.repositories.quota_repository import QuotaRepository
from app.schemas.quota import QuotaListResponse, QuotaStatusResponse, RoleQuotaConfig, RoleQuotaStatus, RoleQuotaUpsert
from app.services.audit_service import AuditService
from app.services.quota_service import QuotaConfigTransition, QuotaService

router = APIRouter(prefix="/admin/quotas", tags=["Admin Quotas"])
_TRANSITION_RECONCILIATION_RETRIES = 3
_QUOTA_LIMIT_FIELDS = (
    "daily_query_limit",
    "daily_execution_limit",
    "daily_export_limit",
)


def _quota_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"error": "service_unavailable", "message_key": "error.service_unavailable"},
    )


def _quota_sync_pending() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": "quota_sync_pending",
            "message_key": "error.quota_sync_pending",
            "mutation_applied": True,
        },
    )


async def _begin_quota_transition(redis: Redis, role_id: uuid.UUID) -> QuotaConfigTransition:
    try:
        return await QuotaService.begin_config_transition(redis, role_id)
    except QuotaUnavailableError as exc:
        raise _quota_unavailable() from exc


async def _publish_quota_transition(
    redis: Redis,
    transition: QuotaConfigTransition,
    quota_config: RoleQuota | None,
    *,
    mutation_applied: bool,
) -> None:
    published = await _try_publish_quota_transition(
        redis,
        transition,
        quota_config,
        mutation_applied=mutation_applied,
    )
    if not published:
        pending_error = _quota_sync_pending() if mutation_applied else _quota_unavailable()
        raise pending_error


async def _try_publish_quota_transition(
    redis: Redis,
    transition: QuotaConfigTransition,
    quota_config: RoleQuota | None,
    *,
    mutation_applied: bool,
) -> bool:
    try:
        return await QuotaService.publish_config_transition(redis, transition, quota_config)
    except QuotaUnavailableError as exc:
        pending_error = _quota_sync_pending() if mutation_applied else _quota_unavailable()
        raise pending_error from exc


async def _locked_role(db: AsyncSession, role_id: uuid.UUID) -> Role | None:
    result = await db.execute(select(Role).where(Role.id == role_id).with_for_update())
    return result.scalar_one_or_none()


def _quota_config(quota: RoleQuota, role_name: str) -> RoleQuotaConfig:
    return RoleQuotaConfig(
        role_id=quota.role_id,
        role_name=role_name,
        daily_query_limit=quota.daily_query_limit,
        daily_execution_limit=quota.daily_execution_limit,
        daily_export_limit=quota.daily_export_limit,
        created_at=quota.created_at,
        updated_at=quota.updated_at,
    )


def _changed_quota_fields(
    quota: RoleQuota | None,
    data: RoleQuotaUpsert,
    fields_set: set[str],
) -> list[str]:
    return [
        field
        for field in _QUOTA_LIMIT_FIELDS
        if field in fields_set and (quota is None or getattr(quota, field) != getattr(data, field))
    ]


async def _log_quota_change(
    db: AsyncSession,
    session: dict,
    role_id: str,
    action: str,
    *,
    changed_fields: list[str] | None = None,
) -> None:
    context: dict[str, object] = {"action": action, "role_id": role_id}
    if changed_fields is not None:
        context["dims_changed"] = changed_fields
    actor_id = uuid.UUID(session["user_id"]) if "user_id" in session else None
    await AuditService.log(
        db,
        action=AuditActionType.QUOTA_CONFIG_CHANGE,
        actor_id=actor_id,
        actor_identity=session.get("user_id"),
        resource_type="role_quota",
        resource_id=role_id,
        outcome="success",
        context=context,
    )


async def _own_transition_after_reconciliation(
    redis: Redis,
    transition: QuotaConfigTransition,
    quota: RoleQuota | None,
    *,
    mutation_applied: bool,
) -> QuotaConfigTransition:
    for _attempt in range(_TRANSITION_RECONCILIATION_RETRIES):
        if transition.created:
            try:
                if await QuotaService.owns_config_transition(redis, transition):
                    return transition
            except QuotaUnavailableError as exc:
                pending_error = _quota_sync_pending() if mutation_applied else _quota_unavailable()
                raise pending_error from exc
        elif await _try_publish_quota_transition(
            redis,
            transition,
            quota,
            mutation_applied=mutation_applied,
        ):
            transition = await _begin_quota_transition(redis, transition.role_id)
            if transition.created:
                return transition
            continue

        transition = await _begin_quota_transition(redis, transition.role_id)

    pending_error = _quota_sync_pending() if mutation_applied else _quota_unavailable()
    raise pending_error


async def _republish_after_rollback(
    db: AsyncSession,
    redis: Redis,
    transition: QuotaConfigTransition,
) -> None:
    await db.rollback()
    await _locked_role(db, transition.role_id)
    quota = await QuotaRepository(db).get(transition.role_id)
    await _publish_quota_transition(
        redis,
        transition,
        quota,
        mutation_applied=False,
    )
    await db.commit()


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
    redis: Redis = Depends(get_redis),  # noqa: B008
):
    from datetime import UTC, datetime, timedelta

    repo = QuotaRepository(db)
    quotas = await repo.list_all()
    now = datetime.now(UTC)
    date_suffix = now.strftime("%Y-%m-%d")
    next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    from app.db.models.user import User

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
                    # Sum usage across all users with this role
                    result = await db.execute(select(User).where(User.role_id == q.role_id))
                    users = list(result.scalars().all())
                    for user in users:
                        key = f"quota:{user.id}:{dim_name}:{date_suffix}"
                        val = await redis.get(key)
                        if val is not None:
                            used += int(val)
                except Exception as exc:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail={
                            "error": "service_unavailable",
                            "message_key": "error.service_unavailable",
                        },
                    ) from exc
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
    data: RoleQuotaUpsert = Depends(validate_body(RoleQuotaUpsert)),  # noqa: B008
    _session: dict = Depends(require_phase6_admin_permission(Permission.ADMIN_QUOTAS_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
):
    """Apply a quota update or return a sanitized synchronization-pending 503.

    A pending response means PostgreSQL and its success audit committed once,
    while quota enforcement remains fail closed until an identical retry
    publishes the authoritative configuration.
    """
    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_uuid", "message_key": "error.validation.invalidUUID"},
        ) from None

    transition = await _begin_quota_transition(redis, role_uuid)
    role = await _locked_role(db, role_uuid)
    if role is None:
        await _publish_quota_transition(
            redis,
            transition,
            None,
            mutation_applied=False,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        )

    fields_set = data.model_fields_set
    repo = QuotaRepository(db)
    existing_quota = await repo.get(role_uuid)
    changed_fields = _changed_quota_fields(existing_quota, data, fields_set)
    transition = await _own_transition_after_reconciliation(
        redis,
        transition,
        existing_quota,
        mutation_applied=existing_quota is not None and not changed_fields,
    )
    if existing_quota is not None and not changed_fields:
        await _publish_quota_transition(
            redis,
            transition,
            existing_quota,
            mutation_applied=True,
        )
        return _quota_config(existing_quota, role.name)

    try:
        quota = await repo.upsert(role_uuid, data, fields_set=fields_set)
        await _log_quota_change(
            db,
            _session,
            role_id,
            "created" if existing_quota is None else "updated",
            changed_fields=changed_fields,
        )
        await db.commit()
    except SQLAlchemyError:
        await _republish_after_rollback(db, redis, transition)
        raise

    await _publish_quota_transition(
        redis,
        transition,
        quota,
        mutation_applied=True,
    )
    return _quota_config(quota, role.name)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quota(
    role_id: str,
    _session: dict = Depends(require_phase6_admin_permission(Permission.ADMIN_QUOTAS_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
):
    """Delete a quota or reconcile a committed deletion before returning 204.

    A pending 503 is retryable and distinct from the preserved 404 response
    for a genuinely unknown, non-pending quota configuration.
    """
    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_uuid", "message_key": "error.validation.invalidUUID"},
        ) from None

    transition = await _begin_quota_transition(redis, role_uuid)
    role = await _locked_role(db, role_uuid)
    if role is None:
        await _publish_quota_transition(
            redis,
            transition,
            None,
            mutation_applied=False,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        )

    repo = QuotaRepository(db)
    existing_quota = await repo.get(role_uuid)
    was_pending = not transition.created
    transition = await _own_transition_after_reconciliation(
        redis,
        transition,
        existing_quota,
        mutation_applied=was_pending and existing_quota is None,
    )
    if existing_quota is None:
        await _publish_quota_transition(
            redis,
            transition,
            None,
            mutation_applied=was_pending,
        )
        if was_pending:
            return
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        )

    try:
        await repo.delete(role_uuid)
        await _log_quota_change(
            db,
            _session,
            role_id,
            "removed",
        )
        await db.commit()
    except SQLAlchemyError:
        await _republish_after_rollback(db, redis, transition)
        raise

    await _publish_quota_transition(
        redis,
        transition,
        None,
        mutation_applied=True,
    )
