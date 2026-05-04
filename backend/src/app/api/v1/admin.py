"""Admin router stubs for Phase 1."""

from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/refresh-schema")
async def refresh_schema():
    """POST /admin/refresh-schema — stub."""
    return {"message": "stub"}
