"""TDD tests for admin SSO provider CRUD endpoints (T-649).

Tests:
- GET /admin/sso/providers — requires admin.sso.manage, returns masked secrets
- POST /admin/sso/providers — requires admin.sso.manage, encrypts secrets,
  rejects duplicate protocol (409), validates required fields
- PUT /admin/sso/providers/{id} — requires admin.sso.manage, encrypts secrets,
  partial update, validates required fields
- DELETE /admin/sso/providers/{id} — requires admin.sso.manage
- All errors sanitized: no raw UUIDs, secrets, certs, metadata XML, DB errors,
  stack traces, or provider internals in user-facing responses.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.schemas.sso import SsoProviderCreate, SsoProviderUpdate

# ── Helpers ───────────────────────────────────────────────────────────────


class FakeResult:
    """Mock SQLAlchemy result with scalars().all() / scalar_one_or_none()."""

    def __init__(self, items):
        self._items = items if isinstance(items, list) else [items]

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def first(self):
        return self._items[0] if self._items else None


def _make_oidc_provider():
    p = MagicMock(spec=SsoProvider)
    p.id = uuid.uuid4()
    p.protocol = SsoProtocol.OIDC
    p.display_name = "Corporate SSO"
    p.issuer_url = "https://idp.example.com"
    p.client_id = "client-id-123"
    p.encrypted_client_secret = "encrypted-secret"
    p.scopes = "openid email profile groups"
    p.redirect_uri = "https://app.example.com/callback"
    p.group_claim_name = "groups"
    p.saml_entity_id = None
    p.saml_metadata_url = None
    p.encrypted_saml_metadata_xml = None
    p.encrypted_saml_certificate = None
    p.is_active = True
    p.created_at = datetime.now(UTC)
    p.updated_at = datetime.now(UTC)
    return p


def _make_saml_provider():
    p = MagicMock(spec=SsoProvider)
    p.id = uuid.uuid4()
    p.protocol = SsoProtocol.SAML
    p.display_name = "SAML IdP"
    p.issuer_url = None
    p.client_id = None
    p.encrypted_client_secret = None
    p.scopes = None
    p.redirect_uri = None
    p.group_claim_name = "groups"
    p.saml_entity_id = "https://app.example.com/sp"
    p.saml_metadata_url = "https://idp.example.com/metadata"
    p.encrypted_saml_metadata_xml = "encrypted-metadata"
    p.encrypted_saml_certificate = "encrypted-cert"
    p.is_active = True
    p.created_at = datetime.now(UTC)
    p.updated_at = datetime.now(UTC)
    return p


# ── Permission Enforcement ────────────────────────────────────────────────


class TestPermissionEnforcement:
    """All admin SSO endpoints require admin.sso.manage permission."""

    @pytest.mark.asyncio
    async def test_get_providers_requires_admin_sso_manage(self):
        from app.api.v1.admin_sso import list_providers

        request = MagicMock()
        request.state.session = {"permissions": ["query.submit"]}

        with pytest.raises(HTTPException) as exc:
            await list_providers(request=request, db=AsyncMock())
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert detail["error"] == "forbidden"
        assert detail["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_create_provider_requires_admin_sso_manage(self):
        from app.api.v1.admin_sso import create_provider

        request = MagicMock()
        request.state.session = {"permissions": ["query.submit"]}

        with pytest.raises(HTTPException) as exc:
            await create_provider(
                request=request,
                body=SsoProviderCreate(protocol="oidc", display_name="Test"),
                db=AsyncMock(),
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_update_provider_requires_admin_sso_manage(self):
        from app.api.v1.admin_sso import update_provider

        request = MagicMock()
        request.state.session = {"permissions": ["query.submit"]}

        with pytest.raises(HTTPException) as exc:
            await update_provider(
                request=request,
                provider_id=str(uuid.uuid4()),
                body=SsoProviderUpdate(),
                db=AsyncMock(),
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_provider_requires_admin_sso_manage(self):
        from app.api.v1.admin_sso import delete_provider

        request = MagicMock()
        request.state.session = {"permissions": ["query.submit"]}

        with pytest.raises(HTTPException) as exc:
            await delete_provider(
                request=request,
                provider_id=str(uuid.uuid4()),
                db=AsyncMock(),
            )
        assert exc.value.status_code == 403


# ── GET /admin/sso/providers ──────────────────────────────────────────────


class TestListProviders:
    """GET /admin/sso/providers returns masked secrets."""

    @pytest.mark.asyncio
    async def test_list_returns_providers_with_masked_secrets(self):
        from app.api.v1.admin_sso import list_providers

        oidc = _make_oidc_provider()
        saml = _make_saml_provider()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([oidc, saml]))

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        result = await list_providers(request=request, db=mock_db)

        providers = result["providers"]
        assert len(providers) == 2

        oidc_resp = next(p for p in providers if p["protocol"] == "oidc")
        assert oidc_resp["client_secret_masked"] == "●●●●●●●●"
        assert "client_secret" not in oidc_resp
        assert oidc_resp["saml_metadata_xml_masked"] == "●●●●●●●●"
        assert oidc_resp["saml_certificate_masked"] == "●●●●●●●●"

        saml_resp = next(p for p in providers if p["protocol"] == "saml")
        assert saml_resp["client_secret_masked"] == "●●●●●●●●"
        assert saml_resp["saml_metadata_xml_masked"] == "●●●●●●●●"
        assert saml_resp["saml_certificate_masked"] == "●●●●●●●●"

    @pytest.mark.asyncio
    async def test_list_empty_returns_empty_providers(self):
        from app.api.v1.admin_sso import list_providers

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([]))

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        result = await list_providers(request=request, db=mock_db)
        assert result["providers"] == []


# ── POST /admin/sso/providers ─────────────────────────────────────────────


class TestCreateProvider:
    """POST /admin/sso/providers creates provider, encrypts secrets, rejects duplicates."""

    @pytest.mark.asyncio
    async def test_create_oidc_encrypts_client_secret(self):
        from app.api.v1.admin_sso import create_provider

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),  # no existing provider for this protocol
                FakeResult([MagicMock()]),  # RETURNING result
            ]
        )
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.add = MagicMock()

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        body = SsoProviderCreate(
            protocol="oidc",
            display_name="New OIDC",
            issuer_url="https://idp.example.com",
            client_id="client-123",
            client_secret="super-secret",
            scopes="openid email",
            redirect_uri="https://app.example.com/callback",
            group_claim_name="groups",
        )

        with patch("app.api.v1.admin_sso.encrypt", return_value="encrypted-value") as mock_encrypt:
            result = await create_provider(request=request, body=body, db=mock_db)

        mock_encrypt.assert_called_once_with("super-secret", ANY)
        assert result["protocol"] == "oidc"
        assert result["client_secret_masked"] == "●●●●●●●●"
        assert "client_secret" not in result

    @pytest.mark.asyncio
    async def test_create_saml_encrypts_metadata_and_certificate(self):
        from app.api.v1.admin_sso import create_provider

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),
                FakeResult([MagicMock()]),
            ]
        )
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.add = MagicMock()

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        body = SsoProviderCreate(
            protocol="saml",
            display_name="New SAML",
            saml_entity_id="https://app.example.com/sp",
            saml_metadata_url="https://idp.example.com/metadata",
            saml_metadata_xml="<xml>metadata</xml>",
            saml_certificate="-----BEGIN CERTIFICATE-----\nMIIB...",
            group_claim_name="groups",
        )

        with patch("app.api.v1.admin_sso.encrypt", return_value="encrypted-value") as mock_encrypt:
            result = await create_provider(request=request, body=body, db=mock_db)

        assert mock_encrypt.call_count == 2
        assert result["protocol"] == "saml"
        assert result["saml_metadata_xml_masked"] == "●●●●●●●●"
        assert result["saml_certificate_masked"] == "●●●●●●●●"

    @pytest.mark.asyncio
    async def test_create_duplicate_protocol_returns_409(self):
        from app.api.v1.admin_sso import create_provider

        existing = _make_oidc_provider()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([existing]))

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        body = SsoProviderCreate(
            protocol="oidc",
            display_name="Duplicate",
            issuer_url="https://idp.example.com",
            client_id="client-123",
            client_secret="secret",
        )

        with pytest.raises(HTTPException) as exc:
            await create_provider(request=request, body=body, db=mock_db)
        assert exc.value.status_code == 409
        detail = exc.value.detail
        assert detail["error"] == "conflict"
        assert "duplicateProtocol" in detail["message_key"]
        # No raw UUIDs or internal details leaked
        assert "uuid" not in str(detail).lower()

    @pytest.mark.asyncio
    async def test_create_oidc_missing_required_fields_returns_422(self):
        from app.api.v1.admin_sso import create_provider

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([]))

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        body = SsoProviderCreate(
            protocol="oidc",
            display_name="Missing Fields",
            # missing issuer_url, client_id, client_secret
        )

        with pytest.raises(HTTPException) as exc:
            await create_provider(request=request, body=body, db=mock_db)
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_create_saml_missing_required_fields_returns_422(self):
        from app.api.v1.admin_sso import create_provider

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([]))

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        body = SsoProviderCreate(
            protocol="saml",
            display_name="Missing Fields",
            # missing saml_entity_id, saml_metadata_url or saml_metadata_xml, saml_certificate
        )

        with pytest.raises(HTTPException) as exc:
            await create_provider(request=request, body=body, db=mock_db)
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_create_error_sanitized_no_raw_secrets(self):
        from app.api.v1.admin_sso import create_provider

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB connection failed: secret=abc123"))

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        body = SsoProviderCreate(
            protocol="oidc",
            display_name="Test",
            issuer_url="https://idp.example.com",
            client_id="client-123",
            client_secret="my-secret",
        )

        with pytest.raises(HTTPException) as exc:
            await create_provider(request=request, body=body, db=mock_db)
        assert exc.value.status_code in (400, 422, 500)
        detail_str = str(exc.value.detail)
        assert "my-secret" not in detail_str
        assert "abc123" not in detail_str
        assert "DB connection failed" not in detail_str


# ── PUT /admin/sso/providers/{id} ────────────────────────────────────────


class TestUpdateProvider:
    """PUT /admin/sso/providers/{id} partial update, encrypts secrets."""

    @pytest.mark.asyncio
    async def test_update_oidc_encrypts_new_client_secret(self):
        from app.api.v1.admin_sso import update_provider

        existing = _make_oidc_provider()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([existing]))
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        body = SsoProviderUpdate(display_name="Updated", client_secret="new-secret")

        with patch("app.api.v1.admin_sso.encrypt", return_value="encrypted-new") as mock_encrypt:
            result = await update_provider(
                request=request,
                provider_id=str(existing.id),
                body=body,
                db=mock_db,
            )

        mock_encrypt.assert_called_once_with("new-secret", ANY)
        assert result["display_name"] == "Updated"
        assert result["client_secret_masked"] == "●●●●●●●●"

    @pytest.mark.asyncio
    async def test_update_saml_encrypts_new_certificate(self):
        from app.api.v1.admin_sso import update_provider

        existing = _make_saml_provider()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([existing]))
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        body = SsoProviderUpdate(saml_certificate="new-cert")

        with patch("app.api.v1.admin_sso.encrypt", return_value="encrypted-new") as mock_encrypt:
            result = await update_provider(
                request=request,
                provider_id=str(existing.id),
                body=body,
                db=mock_db,
            )

        mock_encrypt.assert_called_once_with("new-cert", ANY)
        assert result["saml_certificate_masked"] == "●●●●●●●●"

    @pytest.mark.asyncio
    async def test_update_not_found_returns_404(self):
        from app.api.v1.admin_sso import update_provider

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([]))

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        body = SsoProviderUpdate(display_name="Updated")

        with pytest.raises(HTTPException) as exc:
            await update_provider(
                request=request,
                provider_id=str(uuid.uuid4()),
                body=body,
                db=mock_db,
            )
        assert exc.value.status_code == 404
        detail = exc.value.detail
        assert detail["error"] == "not_found"
        assert "uuid" not in str(detail).lower()

    @pytest.mark.asyncio
    async def test_update_partial_without_secret_preserves_existing(self):
        from app.api.v1.admin_sso import update_provider

        existing = _make_oidc_provider()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([existing]))
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        body = SsoProviderUpdate(display_name="Updated Only")

        with patch("app.api.v1.admin_sso.encrypt") as mock_encrypt:
            result = await update_provider(
                request=request,
                provider_id=str(existing.id),
                body=body,
                db=mock_db,
            )

        mock_encrypt.assert_not_called()
        assert result["display_name"] == "Updated Only"
        assert result["client_secret_masked"] == "●●●●●●●●"

    @pytest.mark.asyncio
    async def test_update_error_sanitized(self):
        from app.api.v1.admin_sso import update_provider

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB error: host=secret-idp.internal"))

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        body = SsoProviderUpdate(display_name="Updated")

        with pytest.raises(HTTPException) as exc:
            await update_provider(
                request=request,
                provider_id=str(uuid.uuid4()),
                body=body,
                db=mock_db,
            )
        detail_str = str(exc.value.detail)
        assert "secret-idp.internal" not in detail_str
        assert "DB error" not in detail_str


# ── DELETE /admin/sso/providers/{id} ──────────────────────────────────────


class TestDeleteProvider:
    """DELETE /admin/sso/providers/{id} removes provider."""

    @pytest.mark.asyncio
    async def test_delete_existing_returns_204(self):
        from app.api.v1.admin_sso import delete_provider

        existing = _make_oidc_provider()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([existing]))
        mock_db.commit = AsyncMock()

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        result = await delete_provider(
            request=request,
            provider_id=str(existing.id),
            db=mock_db,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_not_found_returns_404(self):
        from app.api.v1.admin_sso import delete_provider

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=FakeResult([]))

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        with pytest.raises(HTTPException) as exc:
            await delete_provider(
                request=request,
                provider_id=str(uuid.uuid4()),
                db=mock_db,
            )
        assert exc.value.status_code == 404
        detail = exc.value.detail
        assert detail["error"] == "not_found"
        assert "uuid" not in str(detail).lower()

    @pytest.mark.asyncio
    async def test_delete_error_sanitized(self):
        from app.api.v1.admin_sso import delete_provider

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB error: secret table leak"))

        request = MagicMock()
        request.state.session = {"permissions": ["admin.sso.manage"]}

        with pytest.raises(HTTPException) as exc:
            await delete_provider(
                request=request,
                provider_id=str(uuid.uuid4()),
                db=mock_db,
            )
        detail_str = str(exc.value.detail)
        assert "secret table leak" not in detail_str
