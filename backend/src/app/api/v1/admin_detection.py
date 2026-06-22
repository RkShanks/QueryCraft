"""Phase 6 detection administration routes (T-841).

Endpoints:
- GET /admin/detection/config — get current detection thresholds (admin.security.manage)
- PUT /admin/detection/config — update thresholds, emit DETECTION_CONFIG_CHANGE audit event
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.phase6_permissions import require_phase6_admin_permission
from app.core.dependencies import get_db
from app.db.models.enums import AuditActionType, Permission
from app.repositories.detection_config_repository import DetectionConfigRepository
from app.schemas.detection import DetectionThresholdRead, DetectionThresholdUpdate
from app.services.audit_service import AuditService

router = APIRouter(prefix="/admin/detection", tags=["Admin Detection"])


@router.get("/config", response_model=DetectionThresholdRead)
async def get_detection_config(
    _session: dict = Depends(require_phase6_admin_permission(Permission.ADMIN_SECURITY_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DetectionThresholdRead:
    """Return current detection threshold configuration."""
    repo = DetectionConfigRepository(db)
    row = await repo.get()
    return DetectionThresholdRead(
        block_confidence=row.block_confidence,
        flag_confidence=row.flag_confidence,
        updated_at=row.updated_at,
    )


@router.put("/config", response_model=DetectionThresholdRead)
async def update_detection_config(
    data: DetectionThresholdUpdate,
    _session: dict = Depends(require_phase6_admin_permission(Permission.ADMIN_SECURITY_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DetectionThresholdRead:
    """Update detection threshold configuration and emit audit event.

    FastAPI parses the body as DetectionThresholdUpdate, which validates
    block_confidence > flag_confidence via a Pydantic model_validator.
    Invalid input → FastAPI automatically returns 422 (RequestValidationError).
    Emits DETECTION_CONFIG_CHANGE audit event with sanitized context.
    """

    repo = DetectionConfigRepository(db)
    row = await repo.update(data)

    actor_id = uuid.UUID(_session["user_id"]) if "user_id" in _session else None
    await AuditService.log(
        db,
        action=AuditActionType.DETECTION_CONFIG_CHANGE,
        actor_id=actor_id,
        actor_identity=_session.get("user_id"),
        resource_type="detection_threshold_config",
        resource_id=None,
        outcome="success",
        context={
            "block_confidence_updated": True,
            "flag_confidence_updated": True,
        },
    )

    return DetectionThresholdRead(
        block_confidence=row.block_confidence,
        flag_confidence=row.flag_confidence,
        updated_at=row.updated_at,
    )
