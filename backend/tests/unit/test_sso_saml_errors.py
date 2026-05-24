"""TDD tests for SAML error cases (T-640).

Tests expired assertion, replayed assertion, invalid signature, missing signature.
All errors must be sanitized (no raw assertions, UUIDs, hostnames, certs).
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.services.sso_service import SsoService


class TestSsoServiceSamlErrors:
    """SAML error case unit tests."""

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
            mock_settings.return_value = settings
            service = SsoService(mock_db_session, mock_redis)
            return service

    @pytest.fixture
    def base_attributes(self):
        """Base valid SAML attributes — tests mutate specific fields."""
        now = datetime.now(UTC)
        return {
            "subject_id": "user-subject-123",
            "email": "user@example.com",
            "groups": ["analysts"],
            "issuer": "https://idp.example.com",
            "not_before": (now - timedelta(hours=1)).isoformat(),
            "not_on_or_after": (now + timedelta(hours=1)).isoformat(),
            "assertion_id": "assertion-123",
        }

    @pytest.mark.asyncio
    async def test_expired_assertion_rejected(self, sso_service, saml_provider, mock_redis, base_attributes):
        """Assertion past NotOnOrAfter is rejected."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        base_attributes["not_on_or_after"] = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()

        with patch.object(sso_service, "_parse_saml_assertion", return_value=base_attributes):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        assert (
            "timestamp" in str(exc_info.value).lower()
            or "expir" in str(exc_info.value).lower()
            or "validation" in str(exc_info.value).lower()
            or "saml" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_replayed_assertion_rejected(self, sso_service, saml_provider, mock_redis, base_attributes):
        """Reusing same assertion ID is rejected (replay protection)."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        # assertion ID already exists in Redis
        mock_redis.get.side_effect = [stored, "already-consumed"]

        with patch.object(sso_service, "_parse_saml_assertion", return_value=base_attributes):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        assert (
            "replay" in str(exc_info.value).lower()
            or "assertion" in str(exc_info.value).lower()
            or "validation" in str(exc_info.value).lower()
            or "saml" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_invalid_signature_rejected(self, sso_service, saml_provider, mock_redis, base_attributes):
        """Invalid XML signature raises sanitized error."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        with patch.object(sso_service, "_parse_saml_assertion", side_effect=Exception("Invalid XML signature")):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        error = str(exc_info.value).lower()
        assert "signature" in error or "validation" in error or "saml" in error

    @pytest.mark.asyncio
    async def test_missing_signature_rejected_at_parse_boundary(
        self, sso_service, saml_provider, mock_redis, base_attributes
    ):
        """Unsigned assertion is rejected by python3-saml in _parse_saml_assertion.

        Signature validation is delegated to python3-saml with
        security.wantAssertionsSigned=True; the service does not
        perform a separate has_signature check.
        """
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        with patch.object(sso_service, "_parse_saml_assertion", side_effect=Exception("Signature validation failed")):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        error = str(exc_info.value).lower()
        assert "signature" in error or "validation" in error or "sso" in error

    @pytest.mark.asyncio
    async def test_error_does_not_expose_raw_assertion(self, sso_service, saml_provider, mock_redis, base_attributes):
        """Error messages must never contain raw SAML response or assertion XML."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        base_attributes["issuer"] = "https://evil.com"
        with patch.object(sso_service, "_parse_saml_assertion", return_value=base_attributes):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "raw-saml-xml-here", request_id)

        error_str = str(exc_info.value)
        assert "raw-saml-xml-here" not in error_str
        assert "user-subject-123" not in error_str
        assert "user@example.com" not in error_str

    @pytest.mark.asyncio
    async def test_error_does_not_expose_hostname(self, sso_service, saml_provider, mock_redis, base_attributes):
        """Error messages must not expose IdP hostname or SP URLs."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        base_attributes["issuer"] = "https://evil.com"
        with patch.object(sso_service, "_parse_saml_assertion", return_value=base_attributes):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        assert "https://" not in str(exc_info.value)
        assert "evil.com" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_does_not_expose_uuid(self, sso_service, saml_provider, mock_redis, base_attributes):
        """Error messages must not expose provider UUIDs."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        base_attributes["issuer"] = "https://evil.com"
        with patch.object(sso_service, "_parse_saml_assertion", return_value=base_attributes):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        assert "provider-saml-uuid" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_does_not_expose_encrypted_cert(self, sso_service, saml_provider, mock_redis, base_attributes):
        """Error messages must not expose encrypted certificate."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        base_attributes["issuer"] = "https://evil.com"
        with patch.object(sso_service, "_parse_saml_assertion", return_value=base_attributes):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        assert "enc-cert" not in str(exc_info.value)
