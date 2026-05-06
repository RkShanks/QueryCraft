"""Admin router for Phase 1.

T-119: POST /admin/refresh-schema — force schema introspection cache refresh.
Protected by X-Admin-Key header matching ADMIN_API_KEY env var.
"""

import datetime

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.core.config import get_settings
from app.source_db.connector import SourceDBConnector
from app.source_db.introspector import SchemaIntrospector

router = APIRouter(prefix="/admin", tags=["Admin"])

# Module-level introspector (lives for app lifetime)
_introspector: SchemaIntrospector | None = None


def _get_introspector() -> SchemaIntrospector:
    """Return the shared SchemaIntrospector instance."""
    global _introspector
    if _introspector is None:
        connector = SourceDBConnector()
        _introspector = SchemaIntrospector(
            connector,
            ttl_seconds=get_settings().SCHEMA_CACHE_TTL_SECONDS,
        )
    return _introspector


def _require_admin_key(x_admin_key: str | None) -> None:
    """Validate the X-Admin-Key header against ADMIN_API_KEY.

    Raises:
        HTTPException: 401 if header missing, 403 if key mismatch.
    """
    settings = get_settings()
    expected = settings.ADMIN_API_KEY
    if not x_admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    if not expected or x_admin_key != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message_key": "error.forbidden"},
        )


@router.post("/refresh-schema")
async def refresh_schema(
    request: Request,
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
):
    """POST /admin/refresh-schema — force a schema introspection cache refresh.

    Requires either a valid session (sessionCookie auth per OpenAPI) or
    the X-Admin-Key header (Phase 1 fallback).

    Returns tables_count, columns_count, approximate_tokens, refreshed_at.
    """
    session = getattr(request.state, "session", None)
    if session is None:
        # No valid session — fall back to admin API key
        _require_admin_key(x_admin_key)

    introspector = _get_introspector()
    schema = await introspector.refresh()

    tables_count = len(schema.tables)
    columns_count = sum(len(t.columns) for t in schema.tables)
    approximate_tokens = introspector._count_tokens(schema)

    return {
        "tables_count": tables_count,
        "columns_count": columns_count,
        "approximate_tokens": approximate_tokens,
        "refreshed_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }
