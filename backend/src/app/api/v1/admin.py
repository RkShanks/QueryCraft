"""Admin router for Phase 1.

T-119: POST /admin/refresh-schema — force schema introspection cache refresh.
Protected by X-Admin-Key header matching ADMIN_API_KEY env var.
"""

import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_db
from app.db.models.app_config import AppConfig
from app.schemas.admin_settings import (
    AdminSettingsResponse,
    UpdateAdminSettingsRequest,
    UpdateAdminSettingsResponse,
)
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

    Requires X-Admin-Key header unconditionally (G-006).

    Returns tables_count, columns_count, approximate_tokens, refreshed_at.
    """
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


@router.get("/settings")
async def get_settings_admin(
    request: Request,
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """GET /admin/settings — retrieve admin settings."""
    _require_admin_key(x_admin_key)
    keys = ["llm_context_cap", "max_regenerate_attempts"]
    result = await db.execute(select(AppConfig).where(AppConfig.key.in_(keys)))
    rows = {row.key: int(row.value) for row in result.scalars().all()}
    cap = rows.get("llm_context_cap", 3)
    max_regen = rows.get("max_regenerate_attempts", 3)
    return AdminSettingsResponse(llm_context_cap=cap, max_regenerate_attempts=max_regen)


@router.patch("/settings")
async def update_settings_admin(
    request: Request,
    req: UpdateAdminSettingsRequest,
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """PATCH /admin/settings — update admin settings."""
    _require_admin_key(x_admin_key)
    await db.execute(
        text(
            """
            INSERT INTO app_config (key, value, updated_at)
            VALUES ('llm_context_cap', :cap::jsonb, now())
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = EXCLUDED.updated_at
            """
        ),
        {"cap": str(req.llm_context_cap)},
    )
    await db.execute(
        text(
            """
            INSERT INTO app_config (key, value, updated_at)
            VALUES ('max_regenerate_attempts', :max_regen::jsonb, now())
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = EXCLUDED.updated_at
            """
        ),
        {"max_regen": str(req.max_regenerate_attempts)},
    )
    await db.commit()
    now = datetime.datetime.now(datetime.UTC).isoformat()
    return UpdateAdminSettingsResponse(
        llm_context_cap=req.llm_context_cap,
        max_regenerate_attempts=req.max_regenerate_attempts,
        updated_at=now,
    )
