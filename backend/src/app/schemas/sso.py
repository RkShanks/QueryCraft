"""Phase 5 SSO Pydantic schemas (T-626).

Request/response models for SSO provider configuration and public listing.
Secrets are write-only and masked in responses per S-003.
"""

from pydantic import BaseModel, Field


class SsoProviderPublic(BaseModel):
    """Public SSO provider info for sign-in page."""

    protocol: str
    display_name: str
    login_url: str


class SsoProviderResponse(BaseModel):
    """Admin-facing SSO provider response with masked secrets."""

    id: str
    protocol: str
    display_name: str
    issuer_url: str | None = None
    client_id: str | None = None
    client_secret_masked: str = "●●●●●●●●"
    scopes: str = "openid email profile groups"
    redirect_uri: str | None = None
    group_claim_name: str = "groups"
    saml_entity_id: str | None = None
    saml_metadata_url: str | None = None
    saml_metadata_xml_masked: str = "●●●●●●●●"
    saml_certificate_masked: str = "●●●●●●●●"
    is_active: bool = True
    created_at: str
    updated_at: str


class SsoProviderCreate(BaseModel):
    """Create a new SSO provider (admin only)."""

    protocol: str = Field(..., pattern=r"^(oidc|saml)$")
    display_name: str = Field(..., min_length=1, max_length=200)
    issuer_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    scopes: str = "openid email profile groups"
    redirect_uri: str | None = None
    group_claim_name: str = "groups"
    saml_entity_id: str | None = None
    saml_metadata_url: str | None = None
    saml_metadata_xml: str | None = None
    saml_certificate: str | None = None


class SsoProviderUpdate(BaseModel):
    """Partial update of an SSO provider (admin only)."""

    display_name: str | None = Field(None, min_length=1, max_length=200)
    issuer_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    scopes: str | None = None
    redirect_uri: str | None = None
    group_claim_name: str | None = None
    saml_entity_id: str | None = None
    saml_metadata_url: str | None = None
    saml_metadata_xml: str | None = None
    saml_certificate: str | None = None
    is_active: bool | None = None
