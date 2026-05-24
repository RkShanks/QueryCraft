"""SSO auth router — public SSO endpoints (T-645).

Endpoints:
- GET /auth/sso/providers — list active SSO providers (public, safe fields)
- GET /auth/sso/oidc/login — initiate OIDC flow (redirect to IdP)
- GET /auth/sso/oidc/callback — process OIDC callback (set cookie, redirect)
- GET /auth/sso/saml/login — initiate SAML flow (redirect to IdP)
- POST /auth/sso/saml/callback — process SAML assertion (set cookie, redirect)

Security:
- All errors sanitized — no raw tokens, certs, UUIDs, hostnames, assertion XML
- Errors redirect to /sign-in?error=<safe_code> per api-contracts.md
- Session cookie set via existing SessionMiddleware.set_cookie pattern
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Form, Query, Response
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_redis
from app.core.security import SessionMiddleware
from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.schemas.sso import SsoProviderPublic
from app.services.sso_service import SsoService, SsoValidationError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth/sso", tags=["SSO"])

_SSO_ERROR_MAP: dict[str, str] = {
    "SSO user has no assigned role": "sso_no_role",
    "SSO token expired": "sso_validation_failed",
    "SSO assertion expired": "sso_validation_failed",
    "SSO assertion replay detected": "sso_validation_failed",
    "SSO assertion validation failed": "sso_validation_failed",
    "SSO issuer validation failed": "sso_validation_failed",
    "SSO audience validation failed": "sso_validation_failed",
    "SSO nonce validation failed": "sso_validation_failed",
    "SSO ID token signature validation failed": "sso_validation_failed",
    "SSO token exchange failed": "sso_validation_failed",
    "SSO token response missing ID token": "sso_validation_failed",
    "SSO session expired or invalid": "sso_validation_failed",
    "SSO provider mismatch": "sso_validation_failed",
    "SSO provider configuration incomplete": "sso_provider_unavailable",
    "SSO assertion not yet valid": "sso_validation_failed",
}

_SIGN_IN_URL = "/sign-in"


def _map_sso_error(error: SsoValidationError) -> str:
    """Map SsoValidationError message to a safe error code for redirect."""
    msg = error.message
    for key, code in _SSO_ERROR_MAP.items():
        if key.lower() in msg.lower() or msg.lower() in key.lower():
            return code
    return "sso_validation_failed"


def _error_redirect(error_code: str) -> RedirectResponse:
    """Redirect to sign-in page with safe error code."""
    url = f"{_SIGN_IN_URL}?error={error_code}"
    return RedirectResponse(url=url, status_code=302)


async def _get_sso_service(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
) -> SsoService:
    return SsoService(db, redis)


async def _get_active_providers(db: AsyncSession) -> list[SsoProvider]:
    """Fetch all active SSO providers."""
    stmt = select(SsoProvider).where(SsoProvider.is_active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _get_oidc_provider(db: AsyncSession) -> SsoProvider | None:
    """Fetch the active OIDC provider (single per protocol constraint)."""
    stmt = select(SsoProvider).where(
        SsoProvider.protocol == SsoProtocol.OIDC,
        SsoProvider.is_active.is_(True),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_saml_provider(db: AsyncSession) -> SsoProvider | None:
    """Fetch the active SAML provider (single per protocol constraint)."""
    stmt = select(SsoProvider).where(
        SsoProvider.protocol == SsoProtocol.SAML,
        SsoProvider.is_active.is_(True),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


@router.get("/providers")
async def list_providers(
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """GET /auth/sso/providers — list configured SSO providers for sign-in page."""
    providers = await _get_active_providers(db)
    result = []
    for p in providers:
        login_url = "/api/v1/auth/sso/oidc/login" if p.protocol == SsoProtocol.OIDC else "/api/v1/auth/sso/saml/login"
        result.append(
            SsoProviderPublic(
                protocol=p.protocol,
                display_name=p.display_name,
                login_url=login_url,
            )
        )
    return {"providers": result}


@router.get("/oidc/login")
async def oidc_login(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
):
    """GET /auth/sso/oidc/login — initiate OIDC authorization code flow."""
    sso_service = SsoService(db, redis)
    provider = await _get_oidc_provider(db)
    if provider is None:
        return _error_redirect("sso_not_configured")

    try:
        auth_url = await sso_service.initiate_oidc_login(provider)
        return RedirectResponse(url=auth_url, status_code=302)
    except SsoValidationError as exc:
        logger.warning("oidc_login_failed", error=exc.message)
        return _error_redirect(_map_sso_error(exc))


@router.get("/oidc/callback")
async def oidc_callback(
    code: str = Query(...),
    state: str = Query(...),
    response: Response = None,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
):
    """GET /auth/sso/oidc/callback — process OIDC callback."""
    sso_service = SsoService(db, redis)
    provider = await _get_oidc_provider(db)
    if provider is None:
        return _error_redirect("sso_not_configured")

    try:
        profile, session_id = await sso_service.process_oidc_callback(provider, state, code)
        SessionMiddleware.set_cookie(response, session_id, secure=True)
        return RedirectResponse(url="/", status_code=302)
    except SsoValidationError as exc:
        logger.warning("oidc_callback_failed", error=exc.message)
        return _error_redirect(_map_sso_error(exc))


@router.get("/saml/login")
async def saml_login(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
):
    """GET /auth/sso/saml/login — initiate SAML AuthnRequest."""
    sso_service = SsoService(db, redis)
    provider = await _get_saml_provider(db)
    if provider is None:
        return _error_redirect("sso_not_configured")

    try:
        redirect_url = await sso_service.initiate_saml_login(provider)
        return RedirectResponse(url=redirect_url, status_code=302)
    except SsoValidationError as exc:
        logger.warning("saml_login_failed", error=exc.message)
        return _error_redirect(_map_sso_error(exc))


@router.post("/saml/callback")
async def saml_callback(
    SAMLResponse: str = Form(...),  # noqa: N803
    RelayState: str = Form(...),  # noqa: N803
    response: Response = None,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
):
    """POST /auth/sso/saml/callback — process SAML assertion (ACS endpoint)."""
    sso_service = SsoService(db, redis)
    provider = await _get_saml_provider(db)
    if provider is None:
        return _error_redirect("sso_not_configured")

    try:
        profile, session_id = await sso_service.process_saml_callback(provider, SAMLResponse, RelayState)
        SessionMiddleware.set_cookie(response, session_id, secure=True)
        return RedirectResponse(url="/", status_code=302)
    except SsoValidationError as exc:
        logger.warning("saml_callback_failed", error=exc.message)
        return _error_redirect(_map_sso_error(exc))
