"""History router stubs for Phase 1."""

from fastapi import APIRouter

router = APIRouter(prefix="/history", tags=["History"])


@router.get("")
async def list_history():
    """GET /history — stub."""
    return {"items": []}


@router.get("/{query_id}")
async def get_history_entry(query_id: str):
    """GET /history/{query_id} — stub."""
    return {"message": "stub"}
