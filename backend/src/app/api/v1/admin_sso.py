"""Admin SSO provider configuration endpoints (T-650).

Protected by ``admin.sso.manage`` permission.
Secrets encrypted at rest via AES-256-GCM (``app.core.encryption``).
Responses mask secrets as ``●●●●●●●●`` per S-003.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_db
from app.core.encryption import encrypt
from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.schemas.sso import SsoProviderCreate, SsoProviderUpdate

router = APIRouter(prefix="/admin/sso", tags=["Admin SSO"])


def _check_permission(request: Request) -> None:
    """Verify request has ``admin.sso.manage`` permission."""
    session = getattr(request.state, "session", None)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    user_perms = set(session.get("permissions", []))
    if "admin.sso.manage" not in user_perms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message_key": "error.forbidden"},
        )


def _get_encryption_key() -> str:
    """Return ``PLATFORM_ENCRYPTION_KEY`` from settings."""
    return get_settings().PLATFORM_ENCRYPTION_KEY


def _provider_to_response(provider: SsoProvider) -> dict:
    """Convert ORM provider to masked response dict."""
    return {
        "id": str(provider.id),
        "protocol": provider.protocol,
        "display_name": provider.display_name,
        "issuer_url": provider.issuer_url,
        "client_id": provider.client_id,
        "client_secret_masked": "●●●●●●●●",
        "scopes": provider.scopes or "openid email profile groups",
        "redirect_uri": provider.redirect_uri,
        "group_claim_name": provider.group_claim_name or "groups",
        "saml_entity_id": provider.saml_entity_id,
        "saml_metadata_url": provider.saml_metadata_url,
        "saml_metadata_xml_masked": "●●●●●●●●",
        "saml_certificate_masked": "●●●●●●●●",
        "is_active": provider.is_active,
        "created_at": (provider.created_at.isoformat() if provider.created_at else None),
        "updated_at": (provider.updated_at.isoformat() if provider.updated_at else None),
    }


def _validate_oidc_required(body: SsoProviderCreate | SsoProviderUpdate) -> None:
    """Ensure OIDC provider has required fields."""
    if isinstance(body, SsoProviderCreate):
        if not body.issuer_url or not body.client_id or not body.client_secret:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "message_key": "error.validation.oidcRequiredFields",
                },
            )
    else:
        has_any = body.issuer_url is not None or body.client_id is not None or body.client_secret is not None
        if has_any and (body.issuer_url is None or body.client_id is None):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "message_key": "error.validation.oidcRequiredFields",
                },
            )


def _validate_saml_required(body: SsoProviderCreate | SsoProviderUpdate) -> None:
    """Ensure SAML provider has required fields."""
    if isinstance(body, SsoProviderCreate):
        if not body.saml_entity_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "message_key": "error.validation.samlRequiredFields",
                },
            )
        if not body.saml_metadata_url and not body.saml_metadata_xml:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "message_key": "error.validation.samlRequiredFields",
                },
            )
        if not body.saml_certificate:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "message_key": "error.validation.samlRequiredFields",
                },
            )
    else:
        has_any = (
            body.saml_entity_id is not None
            or body.saml_metadata_url is not None
            or body.saml_metadata_xml is not None
            or body.saml_certificate is not None
        )
        if has_any and not body.saml_entity_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "message_key": "error.validation.samlRequiredFields",
                },
            )
        if has_any and not (body.saml_metadata_url or body.saml_metadata_xml):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "message_key": "error.validation.samlRequiredFields",
                },
            )
        if has_any and not body.saml_certificate:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "message_key": "error.validation.samlRequiredFields",
                },
            )


@router.get("/providers")
async def list_providers(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """GET /admin/sso/providers — list all providers with masked secrets."""
    _check_permission(request)
    try:
        result = await db.execute(select(SsoProvider))
        rows = result.scalars().all()
        return {"providers": [_provider_to_response(p) for p in rows]}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None


@router.post("/providers", status_code=status.HTTP_201_CREATED)
async def create_provider(
    request: Request,
    body: SsoProviderCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """POST /admin/sso/providers — create new provider, encrypt secrets."""
    _check_permission(request)

    if body.protocol == SsoProtocol.OIDC:
        _validate_oidc_required(body)
    elif body.protocol == SsoProtocol.SAML:
        _validate_saml_required(body)

    try:
        existing = await db.execute(select(SsoProvider).where(SsoProvider.protocol == body.protocol))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "conflict",
                    "message_key": "error.conflict.duplicateProtocol",
                },
            )

        key = _get_encryption_key()

        provider = SsoProvider(
            protocol=body.protocol,
            display_name=body.display_name,
            issuer_url=body.issuer_url,
            client_id=body.client_id,
            encrypted_client_secret=(encrypt(body.client_secret, key) if body.client_secret else None),
            scopes=body.scopes,
            redirect_uri=body.redirect_uri,
            group_claim_name=body.group_claim_name,
            saml_entity_id=body.saml_entity_id,
            saml_metadata_url=body.saml_metadata_url,
            encrypted_saml_metadata_xml=(encrypt(body.saml_metadata_xml, key) if body.saml_metadata_xml else None),
            encrypted_saml_certificate=(encrypt(body.saml_certificate, key) if body.saml_certificate else None),
            is_active=True,
        )

        db.add(provider)
        await db.commit()
        await db.refresh(provider)

        return _provider_to_response(provider)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None


@router.put("/providers/{provider_id}")
async def update_provider(
    request: Request,
    provider_id: str,
    body: SsoProviderUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """PUT /admin/sso/providers/{id} — partial update, encrypt new secrets."""
    _check_permission(request)

    try:
        result = await db.execute(select(SsoProvider).where(SsoProvider.id == provider_id))
        provider = result.scalar_one_or_none()
        if provider is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "message_key": "error.notFound",
                },
            )

        key = _get_encryption_key()

        if body.display_name is not None:
            provider.display_name = body.display_name
        if body.issuer_url is not None:
            provider.issuer_url = body.issuer_url
        if body.client_id is not None:
            provider.client_id = body.client_id
        if body.client_secret is not None:
            provider.encrypted_client_secret = encrypt(body.client_secret, key)
        if body.scopes is not None:
            provider.scopes = body.scopes
        if body.redirect_uri is not None:
            provider.redirect_uri = body.redirect_uri
        if body.group_claim_name is not None:
            provider.group_claim_name = body.group_claim_name
        if body.saml_entity_id is not None:
            provider.saml_entity_id = body.saml_entity_id
        if body.saml_metadata_url is not None:
            provider.saml_metadata_url = body.saml_metadata_url
        if body.saml_metadata_xml is not None:
            provider.encrypted_saml_metadata_xml = encrypt(body.saml_metadata_xml, key)
        if body.saml_certificate is not None:
            provider.encrypted_saml_certificate = encrypt(body.saml_certificate, key)
        if body.is_active is not None:
            provider.is_active = body.is_active

        provider.updated_at = datetime.now(UTC)

        await db.commit()
        await db.refresh(provider)

        return _provider_to_response(provider)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    request: Request,
    provider_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """DELETE /admin/sso/providers/{id} — remove provider."""
    _check_permission(request)

    try:
        result = await db.execute(select(SsoProvider).where(SsoProvider.id == provider_id))
        provider = result.scalar_one_or_none()
        if provider is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "message_key": "error.notFound",
                },
            )

        await db.delete(provider)
        await db.commit()

        return None

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None
