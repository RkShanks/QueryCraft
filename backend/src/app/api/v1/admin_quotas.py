"""Phase 6 quota administration route stubs."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.api.v1.phase6_permissions import require_phase6_admin_permission
from app.db.models.enums import Permission

router = APIRouter(prefix="/admin/quotas", tags=["Admin Quotas"])


@router.get("")
async def list_quotas(
    _session: dict = Depends(require_phase6_admin_permission(Permission.ADMIN_QUOTAS_MANAGE)),  # noqa: B008
):
    """Permission-gated placeholder for Wave 18.1 quota listing."""
    return JSONResponse(status_code=status.HTTP_501_NOT_IMPLEMENTED, content={"error": "not_implemented"})
