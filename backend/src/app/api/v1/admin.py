"""Admin router stubs for Phase 1."""

from fastapi import APIRouter, HTTPException, Request, status

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/refresh-schema")
async def refresh_schema(request: Request):
    """POST /admin/refresh-schema — stub."""
    session = getattr(request.state, "session", None)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    import datetime

    return {
        "tables_count": 0,
        "columns_count": 0,
        "approximate_tokens": 0,
        "refreshed_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }
