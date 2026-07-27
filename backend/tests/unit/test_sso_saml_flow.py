"""TDD tests for SAML AuthnRequest initiation (T-638).

Tests AuthnRequest generation, state storage in Redis, and redirect URL.
All external calls mocked — pure unit tests.
"""

import base64
import json
import zlib
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import quote

import pytest

from app.core.encryption import encrypt
from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.services.sso_service import SsoService


class TestSsoServiceSamlInitiation:
    """SAML AuthnRequest initiation unit tests."""

    @pytest.fixture
    def saml_provider(self):
        """A configured SAML provider."""
        provider = MagicMock(spec=SsoProvider)
        provider.id = "provider-saml-uuid"
        provider.protocol = SsoProtocol.SAML
        provider.display_name = "Test SAML"
        provider.saml_entity_id = "https://app.example.com/sp"
        provider.saml_metadata_url = "https://idp.example.com/metadata"
        provider.encrypted_saml_certificate = "enc-cert"
        provider.group_claim_name = "groups"
        return provider

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        redis.get = AsyncMock(return_value=None)
        return redis

    @pytest.fixture
    def mock_db_session(self):
        """Mock async DB session."""
        return AsyncMock()

    @pytest.fixture
    def sso_service(self, mock_db_session, mock_redis):
        """SsoService with mocked dependencies."""
        with patch("app.services.sso_service.get_settings") as mock_settings:
            settings = MagicMock()
            settings.PLATFORM_ENCRYPTION_KEY = "d1OQc28ErbKH8nnhjNbchX5y_1EyXcfclkK1hPjPqFY="
            settings.SESSION_IDLE_TIMEOUT_HOURS = 8
            mock_settings.return_value = settings
            service = SsoService(mock_db_session, mock_redis)
            return service

    def test_raw_deflate_authn_request_is_decoded_for_redirect_rebuild(self, sso_service):
        """Regression: python3-saml emits raw-DEFLATE data for Redirect binding."""
        sso_service._settings.BASE_URL = "http://querycraft.localhost:15173"
        sso_service._settings.PLATFORM_ENCRYPTION_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
        authn_request_xml = "<AuthnRequest ID='p5a-request'/>"
        compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        raw_deflate = compressor.compress(authn_request_xml.encode()) + compressor.flush()
        encoded_request = quote(base64.b64encode(raw_deflate).decode())
        mock_auth = MagicMock()
        mock_auth.login.return_value = f"https://idp.example.com/sso?SAMLRequest={encoded_request}"
        saml_provider = SsoProvider(
            protocol=SsoProtocol.SAML,
            display_name="Test SAML",
            saml_entity_id="https://app.example.com/sp",
            saml_metadata_url="https://idp.example.com/metadata",
            encrypted_saml_certificate=encrypt("test-certificate", sso_service._settings.PLATFORM_ENCRYPTION_KEY),
        )

        with patch("onelogin.saml2.auth.OneLogin_Saml2_Auth", return_value=mock_auth):
            rebuilt_xml = sso_service._build_saml_authn_request(saml_provider, "p5a-request")

        assert rebuilt_xml == authn_request_xml

    @pytest.mark.asyncio
    async def test_initiate_saml_generates_request_id(self, sso_service, saml_provider, mock_redis):
        """AuthnRequest includes a unique request ID stored in Redis."""
        with patch("app.services.sso_service.secrets.token_urlsafe", return_value="test-request-id"):
            with patch.object(
                sso_service, "_build_saml_authn_request", return_value="<AuthnRequest ID='test-request-id'>"
            ) as mock_build:
                await sso_service.initiate_saml_login(saml_provider)

        mock_build.assert_called_once()
        # Verify Redis stored request ID mapping
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        value = call_args[0][1]
        ttl = call_args[1].get("ex")

        assert key.startswith("sso:saml:request:")
        assert "test-request-id" in key
        stored = json.loads(value)
        assert stored["provider_id"] == str(saml_provider.id)
        assert ttl is not None
        assert ttl > 0

    @pytest.mark.asyncio
    async def test_initiate_saml_redirect_url_is_idp_sso_url(self, sso_service, saml_provider):
        """Redirect URL points to IdP SSO endpoint with encoded SAMLRequest."""
        with patch("app.services.sso_service.secrets.token_urlsafe", return_value="req-id"):
            with patch.object(sso_service, "_build_saml_authn_request", return_value="<AuthnRequest>"):
                with patch.object(sso_service, "_get_idp_sso_url", return_value="https://idp.example.com/saml/sso"):
                    redirect_url = await sso_service.initiate_saml_login(saml_provider)

        assert redirect_url.startswith("https://idp.example.com/saml/sso")
        assert "SAMLRequest=" in redirect_url
        assert "RelayState=" in redirect_url

    @pytest.mark.asyncio
    async def test_initiate_saml_redis_key_includes_request_id(self, sso_service, saml_provider, mock_redis):
        """Redis key is scoped by request ID for lookup during callback."""
        with patch("app.services.sso_service.secrets.token_urlsafe", return_value="my-req-789"):
            with patch.object(sso_service, "_build_saml_authn_request", return_value="<AuthnRequest>"):
                await sso_service.initiate_saml_login(saml_provider)

        key = mock_redis.set.call_args[0][0]
        assert key == "sso:saml:request:my-req-789"

    @pytest.mark.asyncio
    async def test_initiate_saml_redis_ttl_matches_session_timeout(self, sso_service, saml_provider, mock_redis):
        """Request ID Redis TTL matches session idle timeout (8h = 28800s)."""
        with patch("app.services.sso_service.secrets.token_urlsafe", return_value="req-id"):
            with patch.object(sso_service, "_build_saml_authn_request", return_value="<AuthnRequest>"):
                await sso_service.initiate_saml_login(saml_provider)

        ttl = mock_redis.set.call_args[1].get("ex")
        assert ttl == 28800

    @pytest.mark.asyncio
    async def test_initiate_saml_sanitized_error_on_missing_entity_id(self, sso_service, saml_provider):
        """Missing entity_id raises sanitized error without exposing internals."""
        saml_provider.saml_entity_id = None
        with pytest.raises(Exception) as exc_info:
            await sso_service.initiate_saml_login(saml_provider)

        error_msg = str(exc_info.value).lower()
        assert "saml" in error_msg or "provider" in error_msg or "configuration" in error_msg
        assert "https://" not in error_msg

    @pytest.mark.asyncio
    async def test_initiate_saml_sanitized_error_on_missing_certificate(self, sso_service, saml_provider):
        """Missing certificate raises sanitized error."""
        saml_provider.encrypted_saml_certificate = None
        with pytest.raises(Exception) as exc_info:
            await sso_service.initiate_saml_login(saml_provider)

        error_msg = str(exc_info.value).lower()
        assert "saml" in error_msg or "provider" in error_msg or "configuration" in error_msg
        assert "enc-cert" not in error_msg

    @pytest.mark.asyncio
    async def test_initiate_saml_no_raw_secrets_in_error(self, sso_service, saml_provider):
        """Error messages must never contain encrypted certificate."""
        saml_provider.saml_entity_id = None
        with pytest.raises(Exception) as exc_info:
            await sso_service.initiate_saml_login(saml_provider)

        assert "enc-cert" not in str(exc_info.value)
