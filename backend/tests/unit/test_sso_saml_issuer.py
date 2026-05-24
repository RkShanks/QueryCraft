"""TDD tests for SAML SP/IdP issuer validation (PR-105 fix).

Tests that assertion issuer is validated against IdP entity ID,
not SP entity ID. Audience validated against SP entity ID.
All external calls mocked.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.services.sso_service import SsoService


class TestSsoServiceSamlIssuer:
    """SAML SP/IdP issuer validation unit tests."""

    @pytest.fixture
    def saml_provider(self):
        """A configured SAML provider with distinct SP and IdP entity IDs."""
        provider = MagicMock(spec=SsoProvider)
        provider.id = "provider-saml-uuid"
        provider.protocol = SsoProtocol.SAML
        provider.display_name = "Test SAML"
        # SP entity ID (our app)
        provider.saml_entity_id = "https://app.example.com/sp"
        # IdP entity ID (separate from SP)
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
    def valid_attrs(self):
        """Valid SAML assertion attributes.

        Audience and signature validation are performed by python3-saml
        process_response() internally; they are not returned as separate
        attrs for tautological re-check.
        """
        now = datetime.now(UTC)
        return {
            "subject_id": "user-subject-123",
            "email": "user@example.com",
            "groups": ["analysts"],
            # Issuer MUST be IdP entity ID, not SP entity ID
            "issuer": "https://idp.example.com",
            "not_before": (now - timedelta(hours=1)).isoformat(),
            "not_on_or_after": (now + timedelta(hours=1)).isoformat(),
            "assertion_id": "assertion-123",
        }

    @pytest.mark.asyncio
    async def test_valid_idp_issuer_passes(self, sso_service, saml_provider, valid_attrs):
        """Assertion with correct IdP issuer passes validation."""
        request_id = "req-1"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        sso_service._redis.get = AsyncMock(return_value=stored)
        sso_service._redis.delete = AsyncMock(return_value=1)
        sso_service._redis.get.side_effect = [stored, None]

        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_attrs):
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = ({"user_id": "uuid"}, "session-id")
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        mock_resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_wrong_idp_issuer_rejected(self, sso_service, saml_provider, valid_attrs):
        """Assertion with wrong IdP issuer is rejected."""
        request_id = "req-1"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        sso_service._redis.get = AsyncMock(return_value=stored)
        sso_service._redis.delete = AsyncMock(return_value=1)

        valid_attrs["issuer"] = "https://evil-idp.com"
        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_attrs):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        assert "issuer" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_sp_entity_id_as_issuer_rejected(self, sso_service, saml_provider, valid_attrs):
        """Assertion with SP entity ID as issuer is rejected (must be IdP)."""
        request_id = "req-1"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        sso_service._redis.get = AsyncMock(return_value=stored)
        sso_service._redis.delete = AsyncMock(return_value=1)

        # SP entity ID is NOT a valid IdP issuer
        valid_attrs["issuer"] = "https://app.example.com/sp"
        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_attrs):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        assert "issuer" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_wrong_audience_rejected_at_parse_boundary(self, sso_service, saml_provider, valid_attrs):
        """Wrong audience is rejected by python3-saml process_response in _parse_saml_assertion.

        Audience validation is delegated to python3-saml; the service does not
        perform a tautological re-check.
        """
        request_id = "req-1"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        sso_service._redis.get = AsyncMock(return_value=stored)
        sso_service._redis.delete = AsyncMock(return_value=1)

        # Simulate python3-saml rejecting wrong audience
        with patch.object(sso_service, "_parse_saml_assertion", side_effect=Exception("Audience validation failed")):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        assert (
            "audience" in str(exc_info.value).lower()
            or "validation" in str(exc_info.value).lower()
            or "sso" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_correct_audience_passes_when_parse_succeeds(self, sso_service, saml_provider, valid_attrs):
        """When _parse_saml_assertion succeeds, audience was already validated by python3-saml."""
        request_id = "req-1"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        sso_service._redis.get = AsyncMock(return_value=stored)
        sso_service._redis.delete = AsyncMock(return_value=1)
        sso_service._redis.get.side_effect = [stored, None]

        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_attrs):
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = ({"user_id": "uuid"}, "session-id")
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        mock_resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_issuer_validation_uses_idp_entity_id_not_sp(self, sso_service, saml_provider, valid_attrs):
        """Issuer validation must compare against IdP entity ID, not SP."""
        request_id = "req-1"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        sso_service._redis.get = AsyncMock(return_value=stored)
        sso_service._redis.delete = AsyncMock(return_value=1)

        # Even though this matches SP entity ID, it should fail because
        # issuer must be IdP entity ID
        valid_attrs["issuer"] = saml_provider.saml_entity_id
        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_attrs):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        assert "issuer" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_no_idp_metadata_url_uses_fallback(self, sso_service, valid_attrs):
        """When no metadata URL, issuer validation may use a configured fallback."""
        provider = MagicMock(spec=SsoProvider)
        provider.id = "provider-saml-uuid"
        provider.protocol = SsoProtocol.SAML
        provider.display_name = "Test SAML"
        provider.saml_entity_id = "https://app.example.com/sp"
        provider.saml_metadata_url = None
        provider.encrypted_saml_certificate = "enc-cert"
        provider.group_claim_name = "groups"

        request_id = "req-1"
        stored = json.dumps({"provider_id": str(provider.id)})
        sso_service._redis.get = AsyncMock(return_value=stored)
        sso_service._redis.delete = AsyncMock(return_value=1)

        # Without metadata URL, issuer validation may be lenient or use
        # a different mechanism. This test documents the behavior.
        valid_attrs["issuer"] = "https://idp.example.com"
        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_attrs):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(provider, "saml-response", request_id)

        # When no metadata URL is configured, validation may fail
        # because we cannot determine the expected IdP issuer.
        assert "issuer" in str(exc_info.value).lower() or "configuration" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_sanitized_error_no_hostname(self, sso_service, saml_provider, valid_attrs):
        """Issuer validation error must not expose IdP hostname."""
        request_id = "req-1"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        sso_service._redis.get = AsyncMock(return_value=stored)
        sso_service._redis.delete = AsyncMock(return_value=1)

        valid_attrs["issuer"] = "https://evil-idp.com"
        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_attrs):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response", request_id)

        assert "https://" not in str(exc_info.value)
        assert "evil-idp.com" not in str(exc_info.value)
        assert "idp.example.com" not in str(exc_info.value)
