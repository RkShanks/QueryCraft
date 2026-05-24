"""TDD tests for python3-saml boundary sanitization (PR-105 fix-3).

Tests that patch OneLogin_Saml2_Auth inside _parse_saml_assertion to prove:
1. settings passed to python3-saml include security.wantAssertionsSigned=True
2. SP entityId equals provider.saml_entity_id (audience validation delegated)
3. process_response() exception with raw XML/hostname/cert becomes sanitized SsoValidationError
4. get_errors() also becomes sanitized SsoValidationError
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.services.sso_service import SsoService, SsoValidationError


class TestSsoServiceSamlBoundary:
    """SAML python3-saml boundary sanitization unit tests."""

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

    def test_settings_include_want_assertions_signed(self, sso_service, saml_provider):
        """python3-saml settings_dict includes security.wantAssertionsSigned=True."""
        captured_settings = {}

        def capture_init(req, settings_dict):
            captured_settings["settings_dict"] = settings_dict
            mock_auth = MagicMock()
            mock_auth.process_response = MagicMock()
            mock_auth.get_errors = MagicMock(return_value=[])
            mock_auth.get_nameid = MagicMock(return_value="user-subject-123")
            mock_auth.get_attribute = MagicMock(return_value=None)
            mock_auth.get_issuer = MagicMock(return_value="https://idp.example.com")
            mock_auth.get_session_not_on_or_after = MagicMock(return_value=None)
            mock_auth.get_last_assertion_id = MagicMock(return_value="assertion-123")
            return mock_auth

        with patch("app.services.sso_service.decrypt", return_value="dummy-cert-pem"):
            with patch("onelogin.saml2.auth.OneLogin_Saml2_Auth", side_effect=capture_init):
                sso_service._parse_saml_assertion(saml_provider, "saml-response-xml")

        assert captured_settings["settings_dict"]["security"]["wantAssertionsSigned"] is True

    def test_sp_entity_id_matches_provider(self, sso_service, saml_provider):
        """SP entityId in settings equals provider.saml_entity_id for audience validation."""
        captured_settings = {}

        def capture_init(req, settings_dict):
            captured_settings["settings_dict"] = settings_dict
            mock_auth = MagicMock()
            mock_auth.process_response = MagicMock()
            mock_auth.get_errors = MagicMock(return_value=[])
            mock_auth.get_nameid = MagicMock(return_value="user-subject-123")
            mock_auth.get_attribute = MagicMock(return_value=None)
            mock_auth.get_issuer = MagicMock(return_value="https://idp.example.com")
            mock_auth.get_session_not_on_or_after = MagicMock(return_value=None)
            mock_auth.get_last_assertion_id = MagicMock(return_value="assertion-123")
            return mock_auth

        with patch("app.services.sso_service.decrypt", return_value="dummy-cert-pem"):
            with patch("onelogin.saml2.auth.OneLogin_Saml2_Auth", side_effect=capture_init):
                sso_service._parse_saml_assertion(saml_provider, "saml-response-xml")

        assert captured_settings["settings_dict"]["sp"]["entityId"] == saml_provider.saml_entity_id

    def test_process_response_exception_sanitized(self, sso_service, saml_provider):
        """process_response() exception with raw XML/hostname/cert becomes sanitized SsoValidationError."""
        raw_error_msg = (
            "Invalid SAMLResponse: <saml:Assertion xmlns:saml='urn:oasis:names:tc:SAML:2.0:assertion'>"
            "Issuer=https://idp.example.com Certificate=MIIDXTCCAkWgAwIBAgIJAJC1HiIA..."
        )

        def mock_init(req, settings_dict):
            mock_auth = MagicMock()
            mock_auth.process_response = MagicMock(side_effect=Exception(raw_error_msg))
            return mock_auth

        with patch("app.services.sso_service.decrypt", return_value="dummy-cert-pem"):
            with patch("onelogin.saml2.auth.OneLogin_Saml2_Auth", side_effect=mock_init):
                with pytest.raises(SsoValidationError) as exc_info:
                    sso_service._parse_saml_assertion(saml_provider, "saml-response-xml")

        error_str = str(exc_info.value)
        assert "SSO assertion validation failed" in error_str
        # Must NOT contain raw XML, hostname, or cert
        assert "saml:Assertion" not in error_str
        assert "idp.example.com" not in error_str
        assert "MIIDXTCCAkWgAwIBAgIJAJC1HiIA" not in error_str
        assert "<" not in error_str
        # Original exception chained
        assert exc_info.value.__cause__ is not None
        assert raw_error_msg in str(exc_info.value.__cause__)

    def test_get_errors_returns_sanitized(self, sso_service, saml_provider):
        """get_errors() with raw details becomes sanitized SsoValidationError."""
        raw_errors = ["Signature validation failed: cert MIIDXTCCAkWgAwIBAgIJAJC1HiIA... host https://idp.example.com"]

        def mock_init(req, settings_dict):
            mock_auth = MagicMock()
            mock_auth.process_response = MagicMock()
            mock_auth.get_errors = MagicMock(return_value=raw_errors)
            return mock_auth

        with patch("app.services.sso_service.decrypt", return_value="dummy-cert-pem"):
            with patch("onelogin.saml2.auth.OneLogin_Saml2_Auth", side_effect=mock_init):
                with pytest.raises(SsoValidationError) as exc_info:
                    sso_service._parse_saml_assertion(saml_provider, "saml-response-xml")

        error_str = str(exc_info.value)
        assert "SSO assertion validation failed" in error_str
        # Must NOT contain raw cert, hostname
        assert "MIIDXTCCAkWgAwIBAgIJAJC1HiIA" not in error_str
        assert "idp.example.com" not in error_str
        assert "https://" not in error_str
        # get_errors() result is not directly exposed
        assert "Signature validation failed" not in error_str

    def test_process_response_exception_no_hostname(self, sso_service, saml_provider):
        """Sanitized error must not expose IdP hostname even when process_response raises."""
        raw_error_msg = "Connection refused to https://idp.example.com:8443/saml/sso"

        def mock_init(req, settings_dict):
            mock_auth = MagicMock()
            mock_auth.process_response = MagicMock(side_effect=Exception(raw_error_msg))
            return mock_auth

        with patch("app.services.sso_service.decrypt", return_value="dummy-cert-pem"):
            with patch("onelogin.saml2.auth.OneLogin_Saml2_Auth", side_effect=mock_init):
                with pytest.raises(SsoValidationError) as exc_info:
                    sso_service._parse_saml_assertion(saml_provider, "saml-response-xml")

        error_str = str(exc_info.value)
        assert "idp.example.com" not in error_str
        assert "8443" not in error_str
        assert "https://" not in error_str
        # Original exception chained (for debugging, not user-facing)
        assert raw_error_msg in str(exc_info.value.__cause__)

    def test_get_errors_no_raw_xml(self, sso_service, saml_provider):
        """Sanitized error must not contain raw assertion XML when get_errors returns details."""
        raw_errors = ["SAMLResponse invalid: <saml:Assertion ID='assertion-1'>..."]

        def mock_init(req, settings_dict):
            mock_auth = MagicMock()
            mock_auth.process_response = MagicMock()
            mock_auth.get_errors = MagicMock(return_value=raw_errors)
            return mock_auth

        with patch("app.services.sso_service.decrypt", return_value="dummy-cert-pem"):
            with patch("onelogin.saml2.auth.OneLogin_Saml2_Auth", side_effect=mock_init):
                with pytest.raises(SsoValidationError) as exc_info:
                    sso_service._parse_saml_assertion(saml_provider, "saml-response-xml")

        error_str = str(exc_info.value)
        assert "saml:Assertion" not in error_str
        assert "assertion-1" not in error_str
        assert "<" not in error_str
