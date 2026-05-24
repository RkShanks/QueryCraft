"""TDD tests for SSO auth endpoints (T-645).

Tests for:
- GET /auth/sso/providers — public, returns safe provider info
- GET /auth/sso/oidc/login — redirects to IdP
- GET /auth/sso/oidc/callback — validates callback, sets cookie, redirects
- GET /auth/sso/saml/login — redirects to IdP
- POST /auth/sso/saml/callback — validates assertion, sets cookie, redirects
- All errors sanitized (no raw tokens, certs, UUIDs, hostnames, assertion XML)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.responses import RedirectResponse

from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.services.sso_service import SsoValidationError


def _make_oidc_provider():
    provider = MagicMock(spec=SsoProvider)
    provider.id = "oidc-uuid-1234"
    provider.protocol = SsoProtocol.OIDC
    provider.display_name = "Corporate SSO"
    provider.issuer_url = "https://idp.example.com"
    provider.client_id = "test-client-id"
    provider.encrypted_client_secret = "enc-secret"
    provider.scopes = "openid email profile groups"
    provider.redirect_uri = "https://app.example.com/api/v1/auth/sso/oidc/callback"
    provider.group_claim_name = "groups"
    provider.saml_entity_id = None
    provider.saml_metadata_url = None
    provider.encrypted_saml_certificate = None
    provider.encrypted_saml_metadata_xml = None
    provider.is_active = True
    return provider


def _make_saml_provider():
    provider = MagicMock(spec=SsoProvider)
    provider.id = "saml-uuid-5678"
    provider.protocol = SsoProtocol.SAML
    provider.display_name = "SAML Provider"
    provider.issuer_url = None
    provider.client_id = None
    provider.encrypted_client_secret = None
    provider.scopes = None
    provider.redirect_uri = None
    provider.group_claim_name = "groups"
    provider.saml_entity_id = "https://app.example.com/sp"
    provider.saml_metadata_url = "https://idp.example.com/metadata"
    provider.encrypted_saml_certificate = "enc-cert"
    provider.encrypted_saml_metadata_xml = None
    provider.is_active = True
    return provider


class TestErrorMapping:
    """Tests for SSO error → safe error code mapping."""

    def test_no_role_maps_to_sso_no_role(self):
        from app.api.v1.sso_auth import _map_sso_error

        exc = SsoValidationError("SSO user has no assigned role")
        assert _map_sso_error(exc) == "sso_no_role"

    def test_expired_token_maps_to_validation_failed(self):
        from app.api.v1.sso_auth import _map_sso_error

        exc = SsoValidationError("SSO token expired")
        assert _map_sso_error(exc) == "sso_validation_failed"

    def test_replay_maps_to_validation_failed(self):
        from app.api.v1.sso_auth import _map_sso_error

        exc = SsoValidationError("SSO assertion replay detected")
        assert _map_sso_error(exc) == "sso_validation_failed"

    def test_provider_incomplete_maps_to_unavailable(self):
        from app.api.v1.sso_auth import _map_sso_error

        exc = SsoValidationError("SSO provider configuration incomplete")
        assert _map_sso_error(exc) == "sso_provider_unavailable"

    def test_unknown_error_defaults_to_validation_failed(self):
        from app.api.v1.sso_auth import _map_sso_error

        exc = SsoValidationError("Something unexpected")
        assert _map_sso_error(exc) == "sso_validation_failed"


class TestErrorRedirect:
    """Tests for _error_redirect helper."""

    def test_returns_redirect_to_sign_in_with_error_code(self):
        from app.api.v1.sso_auth import _error_redirect

        response = _error_redirect("sso_validation_failed")
        assert response.status_code == 302
        assert "/sign-in?error=sso_validation_failed" in response.headers["location"]

    def test_no_raw_secrets_in_redirect_url(self):
        from app.api.v1.sso_auth import _error_redirect

        response = _error_redirect("sso_no_role")
        location = response.headers["location"]
        assert "token" not in location.lower() or "sso" in location
        assert "certificate" not in location.lower()
        assert "uuid" not in location.lower()


class TestGetActiveProviders:
    """Tests for _get_active_providers helper."""

    @pytest.mark.asyncio
    async def test_returns_active_providers(self):
        from app.api.v1.sso_auth import _get_active_providers

        oidc = _make_oidc_provider()
        saml = _make_saml_provider()
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [oidc, saml]
        mock_db.execute = AsyncMock(return_value=mock_result)

        providers = await _get_active_providers(mock_db)
        assert len(providers) == 2


class TestListProvidersEndpoint:
    """Tests for the providers response schema — no secrets in output."""

    @pytest.mark.asyncio
    async def test_provider_public_schema_no_secrets(self):
        from app.schemas.sso import SsoProviderPublic

        p = SsoProviderPublic(
            protocol="oidc",
            display_name="Corporate SSO",
            login_url="/api/v1/auth/sso/oidc/login",
        )
        data = p.model_dump()
        assert "protocol" in data
        assert "display_name" in data
        assert "login_url" in data
        assert "encrypted_client_secret" not in data
        assert "encrypted_saml_certificate" not in data
        assert "client_id" not in data


class TestOidcLoginEndpoint:
    """GET /auth/sso/oidc/login — redirect to IdP."""

    @pytest.mark.asyncio
    async def test_success_redirects_to_idp(self):
        from app.api.v1.sso_auth import oidc_login

        oidc = _make_oidc_provider()
        mock_redis = AsyncMock()
        mock_sso_service = AsyncMock()
        mock_sso_service.initiate_oidc_login = AsyncMock(return_value="https://idp.example.com/authorize?state=abc")

        with patch("app.api.v1.sso_auth._get_oidc_provider", new_callable=AsyncMock, return_value=oidc):
            with patch("app.api.v1.sso_auth.SsoService", return_value=mock_sso_service):
                response = await oidc_login(db=AsyncMock(), redis=mock_redis)

        assert response.status_code == 302
        assert "idp.example.com" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_no_provider_redirects_not_configured(self):
        from app.api.v1.sso_auth import oidc_login

        mock_redis = AsyncMock()
        with patch("app.api.v1.sso_auth._get_oidc_provider", new_callable=AsyncMock, return_value=None):
            response = await oidc_login(db=AsyncMock(), redis=mock_redis)

        assert response.status_code == 302
        assert "sso_not_configured" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_validation_error_redirects_sanitized(self):
        from app.api.v1.sso_auth import oidc_login

        oidc = _make_oidc_provider()
        mock_redis = AsyncMock()
        mock_sso_service = AsyncMock()
        mock_sso_service.initiate_oidc_login = AsyncMock(
            side_effect=SsoValidationError("SSO provider configuration incomplete")
        )

        with patch("app.api.v1.sso_auth._get_oidc_provider", new_callable=AsyncMock, return_value=oidc):
            with patch("app.api.v1.sso_auth.SsoService", return_value=mock_sso_service):
                response = await oidc_login(db=AsyncMock(), redis=mock_redis)

        assert response.status_code == 302
        location = response.headers["location"]
        assert "error=" in location
        assert (
            "sso_provider_unavailable" in location
            or "sso_validation_failed" in location
            or "sso_not_configured" in location
        )


class TestOidcCallbackEndpoint:
    """GET /auth/sso/oidc/callback — process OIDC callback."""

    @pytest.mark.asyncio
    async def test_success_sets_cookie_and_redirects(self):
        from app.api.v1.sso_auth import oidc_callback

        oidc = _make_oidc_provider()
        profile = {
            "user_id": "user-uuid",
            "username": "user@example.com",
            "display_name": "User",
            "role_id": "role-uuid",
            "role_name": "Analyst",
            "permissions": ["query.submit"],
            "auth_provider": "oidc",
            "subject_id": "sub-1",
        }
        mock_sso_service = AsyncMock()
        mock_sso_service.process_oidc_callback = AsyncMock(return_value=(profile, "session-id-123"))

        with patch("app.api.v1.sso_auth._get_oidc_provider", new_callable=AsyncMock, return_value=oidc):
            with patch("app.api.v1.sso_auth.SsoService", return_value=mock_sso_service):
                response = await oidc_callback(
                    code="auth-code",
                    state="test-state",
                    db=AsyncMock(),
                    redis=AsyncMock(),
                )

        assert response.status_code == 302
        cookie_header = response.headers.get("set-cookie", "")
        assert "session_id=session-id-123" in cookie_header
        assert "HttpOnly" in cookie_header
        assert "SameSite=strict" in cookie_header
        assert "Secure" in cookie_header

    @pytest.mark.asyncio
    async def test_success_cookie_on_redirect_not_on_separate_response(self):
        from app.api.v1.sso_auth import oidc_callback

        oidc = _make_oidc_provider()
        profile = {
            "user_id": "user-uuid",
            "username": "user@example.com",
            "display_name": "User",
            "role_id": "role-uuid",
            "role_name": "Analyst",
            "permissions": ["query.submit"],
            "auth_provider": "oidc",
            "subject_id": "sub-1",
        }
        mock_sso_service = AsyncMock()
        mock_sso_service.process_oidc_callback = AsyncMock(return_value=(profile, "session-id-123"))

        with patch("app.api.v1.sso_auth._get_oidc_provider", new_callable=AsyncMock, return_value=oidc):
            with patch("app.api.v1.sso_auth.SsoService", return_value=mock_sso_service):
                response = await oidc_callback(
                    code="auth-code",
                    state="test-state",
                    db=AsyncMock(),
                    redis=AsyncMock(),
                )

        assert isinstance(response, RedirectResponse)
        cookie_header = response.headers.get("set-cookie", "")
        assert "session_id=" in cookie_header, "Cookie must be on the returned RedirectResponse, not a separate response object"

    @pytest.mark.asyncio
    async def test_validation_error_redirects_with_sso_error(self):
        from app.api.v1.sso_auth import oidc_callback

        oidc = _make_oidc_provider()
        mock_sso_service = AsyncMock()
        mock_sso_service.process_oidc_callback = AsyncMock(side_effect=SsoValidationError("SSO token expired"))

        with patch("app.api.v1.sso_auth._get_oidc_provider", new_callable=AsyncMock, return_value=oidc):
            with patch("app.api.v1.sso_auth.SsoService", return_value=mock_sso_service):
                response = await oidc_callback(
                    code="auth-code",
                    state="test-state",
                    db=AsyncMock(),
                    redis=AsyncMock(),
                )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "error=" in location
        raw_forbidden = ["token expired", "certificate", "user-uuid"]
        for word in raw_forbidden:
            assert word not in location

    @pytest.mark.asyncio
    async def test_no_role_redirects_with_sso_no_role(self):
        from app.api.v1.sso_auth import oidc_callback

        oidc = _make_oidc_provider()
        mock_sso_service = AsyncMock()
        mock_sso_service.process_oidc_callback = AsyncMock(
            side_effect=SsoValidationError("SSO user has no assigned role")
        )

        with patch("app.api.v1.sso_auth._get_oidc_provider", new_callable=AsyncMock, return_value=oidc):
            with patch("app.api.v1.sso_auth.SsoService", return_value=mock_sso_service):
                response = await oidc_callback(
                    code="auth-code",
                    state="test-state",
                    db=AsyncMock(),
                    redis=AsyncMock(),
                )

        assert response.status_code == 302
        assert "sso_no_role" in response.headers["location"]


class TestSamlLoginEndpoint:
    """GET /auth/sso/saml/login — redirect to IdP."""

    @pytest.mark.asyncio
    async def test_success_redirects_to_idp(self):
        from app.api.v1.sso_auth import saml_login

        saml = _make_saml_provider()
        mock_redis = AsyncMock()
        mock_sso_service = AsyncMock()
        mock_sso_service.initiate_saml_login = AsyncMock(return_value="https://idp.example.com/sso?SAMLRequest=abc")

        with patch("app.api.v1.sso_auth._get_saml_provider", new_callable=AsyncMock, return_value=saml):
            with patch("app.api.v1.sso_auth.SsoService", return_value=mock_sso_service):
                response = await saml_login(db=AsyncMock(), redis=mock_redis)

        assert response.status_code == 302
        assert "idp.example.com" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_no_provider_redirects_not_configured(self):
        from app.api.v1.sso_auth import saml_login

        with patch("app.api.v1.sso_auth._get_saml_provider", new_callable=AsyncMock, return_value=None):
            response = await saml_login(db=AsyncMock(), redis=AsyncMock())

        assert response.status_code == 302
        assert "sso_not_configured" in response.headers["location"]


class TestSamlCallbackEndpoint:
    """POST /auth/sso/saml/callback — process SAML assertion."""

    @pytest.mark.asyncio
    async def test_success_sets_cookie_and_redirects(self):
        from app.api.v1.sso_auth import saml_callback

        saml = _make_saml_provider()
        profile = {
            "user_id": "user-uuid",
            "username": "user@example.com",
            "display_name": "User",
            "role_id": "role-uuid",
            "role_name": "Analyst",
            "permissions": ["query.submit"],
            "auth_provider": "saml",
            "subject_id": "sub-1",
        }
        mock_sso_service = AsyncMock()
        mock_sso_service.process_saml_callback = AsyncMock(return_value=(profile, "session-id-456"))

        with patch("app.api.v1.sso_auth._get_saml_provider", new_callable=AsyncMock, return_value=saml):
            with patch("app.api.v1.sso_auth.SsoService", return_value=mock_sso_service):
                response = await saml_callback(
                    SAMLResponse="base64-saml-response",
                    RelayState="request-id-1",
                    db=AsyncMock(),
                    redis=AsyncMock(),
                )

        assert response.status_code == 302
        cookie_header = response.headers.get("set-cookie", "")
        assert "session_id=session-id-456" in cookie_header
        assert "HttpOnly" in cookie_header
        assert "SameSite=strict" in cookie_header
        assert "Secure" in cookie_header

    @pytest.mark.asyncio
    async def test_success_cookie_on_redirect_not_on_separate_response(self):
        from app.api.v1.sso_auth import saml_callback

        saml = _make_saml_provider()
        profile = {
            "user_id": "user-uuid",
            "username": "user@example.com",
            "display_name": "User",
            "role_id": "role-uuid",
            "role_name": "Analyst",
            "permissions": ["query.submit"],
            "auth_provider": "saml",
            "subject_id": "sub-1",
        }
        mock_sso_service = AsyncMock()
        mock_sso_service.process_saml_callback = AsyncMock(return_value=(profile, "session-id-456"))

        with patch("app.api.v1.sso_auth._get_saml_provider", new_callable=AsyncMock, return_value=saml):
            with patch("app.api.v1.sso_auth.SsoService", return_value=mock_sso_service):
                response = await saml_callback(
                    SAMLResponse="base64-saml-response",
                    RelayState="request-id-1",
                    db=AsyncMock(),
                    redis=AsyncMock(),
                )

        assert isinstance(response, RedirectResponse)
        cookie_header = response.headers.get("set-cookie", "")
        assert "session_id=" in cookie_header, "Cookie must be on the returned RedirectResponse, not a separate response object"

    @pytest.mark.asyncio
    async def test_validation_error_redirects_with_sso_error(self):
        from app.api.v1.sso_auth import saml_callback

        saml = _make_saml_provider()
        mock_sso_service = AsyncMock()
        mock_sso_service.process_saml_callback = AsyncMock(
            side_effect=SsoValidationError("SSO assertion replay detected")
        )

        with patch("app.api.v1.sso_auth._get_saml_provider", new_callable=AsyncMock, return_value=saml):
            with patch("app.api.v1.sso_auth.SsoService", return_value=mock_sso_service):
                response = await saml_callback(
                    SAMLResponse="base64-saml-response",
                    RelayState="request-id-1",
                    db=AsyncMock(),
                    redis=AsyncMock(),
                )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "error=" in location
        raw_forbidden = ["replay detected", "assertion-xml", "certificate"]
        for word in raw_forbidden:
            assert word not in location

    @pytest.mark.asyncio
    async def test_saml_callback_no_assertion_xml_in_redirect(self):
        from app.api.v1.sso_auth import saml_callback

        saml = _make_saml_provider()
        mock_sso_service = AsyncMock()
        mock_sso_service.process_saml_callback = AsyncMock(
            side_effect=SsoValidationError("SSO assertion validation failed")
        )

        with patch("app.api.v1.sso_auth._get_saml_provider", new_callable=AsyncMock, return_value=saml):
            with patch("app.api.v1.sso_auth.SsoService", return_value=mock_sso_service):
                response = await saml_callback(
                    SAMLResponse="<samlp:Response><Assertion>secret-xml</Assertion></samlp:Response>",
                    RelayState="request-id-1",
                    db=AsyncMock(),
                    redis=AsyncMock(),
                )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "Assertion" not in location
        assert "secret-xml" not in location
        assert "samlp" not in location
