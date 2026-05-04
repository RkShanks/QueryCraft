"""Auth router stubs for Phase 1."""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/sign-in")
async def sign_in():
    """POST /auth/sign-in — stub."""
    return {"message": "stub"}


@router.post("/sign-out", status_code=204)
async def sign_out():
    """POST /auth/sign-out — stub."""
    return None


@router.get("/me")
async def get_me():
    """GET /auth/me — stub."""
    return {"message": "stub"}
