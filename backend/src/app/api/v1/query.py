"""Query router stubs for Phase 1."""

from fastapi import APIRouter

router = APIRouter(prefix="/query", tags=["Query"])


@router.post("/submit")
async def submit_question():
    """POST /query/submit — stub."""
    return {"message": "stub"}


@router.post("/accept", status_code=201)
async def accept_query():
    """POST /query/accept — stub."""
    return {"message": "stub"}


@router.post("/reject")
async def reject_query():
    """POST /query/reject — stub."""
    return {"message": "stub"}


@router.post("/regenerate")
async def regenerate_query():
    """POST /query/regenerate — stub."""
    return {"message": "stub"}
