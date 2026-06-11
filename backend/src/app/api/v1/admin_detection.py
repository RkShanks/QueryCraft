"""Phase 6 detection administration route stubs."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.phase6_permissions import require_phase6_admin_permission
from app.db.models.enums import Permission

router = APIRouter(prefix="/admin/detection", tags=["Admin Detection"])


@router.get("/config")
async def get_detection_config(
    _session: dict = Depends(require_phase6_admin_permission(Permission.ADMIN_SECURITY_MANAGE)),  # noqa: B008
):
    """Permission-gated placeholder for Wave 18.2 detection config."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"error": "not_implemented", "message_key": "error.not_implemented"},
    )
