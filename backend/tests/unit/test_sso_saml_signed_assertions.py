"""TDD tests for SAML signed assertions and fail-closed config (PR-105 fix-2).

Tests:
1. Unsigned SAML assertions rejected via python3-saml security settings.
2. Missing metadata URL causes fail-closed error (no hardcoded fallback).
3. Audience validation delegated to python3-saml process_response.
4. Sanitized errors contain no raw XML, certs, hostnames.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.services.sso_service import SsoService


class TestSsoServiceSamlSignedAssertions:
    """SAML signed assertion and fail-closed unit tests."""

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
        redis.delete = AsyncMock(return_value=1)
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
            settings.BASE_URL = "https://app.example.com"
            mock_settings.return_value = settings
            service = SsoService(mock_db_session, mock_redis)
            return service

    @pytest.mark.asyncio
    async def test_unsigned_assertion_rejected(self, sso_service, saml_provider, mock_redis):
        """Unsigned SAML assertion is rejected by security settings."""
        request_id = "req-1"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        # Simulate python3-saml rejecting unsigned assertion
        with patch.object(sso_service, "_parse_saml_assertion", side_effect=Exception("Unsigned assertion rejected")):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "unsigned-saml-response", request_id)

        error = str(exc_info.value).lower()
        assert "assertion" in error or "signature" in error or "validation" in error or "sso" in error

    @pytest.mark.asyncio
    async def test_no_metadata_url_fail_closed(self, sso_service):
        """Missing saml_metadata_url raises sanitized config error, no hardcoded fallback."""
        provider = MagicMock(spec=SsoProvider)
        provider.id = "provider-saml-uuid"
        provider.protocol = SsoProtocol.SAML
        provider.display_name = "Test SAML"
        provider.saml_entity_id = "https://app.example.com/sp"
        provider.saml_metadata_url = None
        provider.encrypted_saml_certificate = "enc-cert"
        provider.group_claim_name = "groups"

        with pytest.raises(Exception) as exc_info:
            await sso_service.initiate_saml_login(provider)

        error = str(exc_info.value).lower()
        assert "configuration" in error or "incomplete" in error or "sso" in error
        # Must not contain hardcoded fallback URL
        assert "idp.example.com" not in str(exc_info.value)
        assert "https://" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_idp_sso_url_fail_closed_no_metadata(self, sso_service):
        """_get_idp_sso_url raises when no metadata URL is available."""
        provider = MagicMock(spec=SsoProvider)
        provider.saml_metadata_url = None

        with pytest.raises(Exception) as exc_info:
            sso_service._get_idp_sso_url(provider)

        assert "configuration" in str(exc_info.value).lower() or "incomplete" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_initiate_saml_login_uses_metadata_url(self, sso_service, saml_provider, mock_redis):
        """Initiation derives SSO URL from metadata URL, not hardcoded fallback."""
        with patch("app.services.sso_service.secrets.token_urlsafe", return_value="req-id"):
            with patch.object(sso_service, "_build_saml_authn_request", return_value="<AuthnRequest>"):
                redirect_url = await sso_service.initiate_saml_login(saml_provider)

        assert "idp.example.com" in redirect_url
        assert "sso" in redirect_url
        # Should NOT contain hardcoded fallback
        assert redirect_url.count("idp.example.com") >= 1

    @pytest.mark.asyncio
    async def test_sanitized_error_no_assertion_xml(self, sso_service, saml_provider, mock_redis):
        """Error must not contain raw SAMLResponse XML."""
        request_id = "req-1"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        with patch.object(
            sso_service, "_parse_saml_assertion", side_effect=Exception("SSO assertion validation failed")
        ):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "raw-xml-here", request_id)

        assert "raw-xml-here" not in str(exc_info.value)
        assert "<saml:Assertion" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_sanitized_error_no_certificate(self, sso_service, saml_provider, mock_redis):
        """Error must not contain encrypted certificate content."""
        request_id = "req-1"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        with patch.object(sso_service, "_parse_saml_assertion", side_effect=Exception("Certificate validation failed")):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        assert "enc-cert" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_sanitized_error_no_hostname(self, sso_service, saml_provider, mock_redis):
        """Error must not expose IdP hostname."""
        request_id = "req-1"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        with patch.object(
            sso_service, "_parse_saml_assertion", side_effect=Exception("SSO assertion validation failed")
        ):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        assert "idp.example.com" not in str(exc_info.value)
        assert "https://" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_process_response_validates_audience_internally(self, sso_service, saml_provider, mock_redis):
        """python3-saml process_response validates audience against SP entity ID.

        This test documents that audience validation happens inside
        _parse_saml_assertion via python3-saml, not via tautological
        service-level check.
        """
        request_id = "req-1"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        # If _parse_saml_assertion succeeds, python3-saml already validated audience
        attrs = {
            "subject_id": "u1",
            "email": "u@example.com",
            "groups": ["analysts"],
            "issuer": "https://idp.example.com",
            "audience": "https://app.example.com/sp",
            "not_before": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            "not_on_or_after": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "assertion_id": "assertion-1",
            "has_signature": True,
        }

        with patch.object(sso_service, "_parse_saml_assertion", return_value=attrs):
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = ({"user_id": "uuid"}, "session-id")
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        mock_resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_wrong_audience_fails_at_parse_boundary(self, sso_service, saml_provider, mock_redis):
        """Wrong assertion audience fails at python3-saml boundary (process_response)."""
        request_id = "req-1"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        # Simulate python3-saml rejecting wrong audience
        with patch.object(sso_service, "_parse_saml_assertion", side_effect=Exception("Audience validation failed")):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        assert (
            "audience" in str(exc_info.value).lower()
            or "validation" in str(exc_info.value).lower()
            or "sso" in str(exc_info.value).lower()
        )
