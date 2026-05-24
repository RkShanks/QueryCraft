"""TDD tests for SAML callback validation (T-639).

Tests assertion validation per S-002: issuer, audience, signature,
timestamps, replay protection. All external calls mocked.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.services.sso_service import SsoService


class TestSsoServiceSamlCallback:
    """SAML callback validation unit tests."""

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
    def valid_saml_attributes(self):
        """Valid SAML assertion attributes."""
        now = datetime.now(UTC)
        return {
            "subject_id": "user-subject-123",
            "email": "user@example.com",
            "groups": ["analysts", "data-team"],
            "issuer": "https://idp.example.com",
            "not_before": (now - timedelta(hours=1)).isoformat(),
            "not_on_or_after": (now + timedelta(hours=1)).isoformat(),
            "assertion_id": "assertion-123",
        }

    @pytest.mark.asyncio
    async def test_callback_validates_issuer_matches_entity_id(
        self, sso_service, saml_provider, mock_redis, valid_saml_attributes
    ):
        """Assertion issuer must match configured IdP entity ID."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.return_value = stored

        valid_saml_attributes["issuer"] = "https://evil-idp.com"
        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_saml_attributes):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response-xml", request_id)

        assert (
            "issuer" in str(exc_info.value).lower()
            or "validation" in str(exc_info.value).lower()
            or "saml" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_callback_audience_rejected_at_parse_boundary(
        self, sso_service, saml_provider, mock_redis, valid_saml_attributes
    ):
        """Wrong assertion audience is rejected by python3-saml in _parse_saml_assertion.

        Audience validation is delegated to python3-saml process_response();
        the service does not perform a tautological re-check.
        """
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.return_value = stored

        with patch.object(sso_service, "_parse_saml_assertion", side_effect=Exception("Audience validation failed")):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response-xml", request_id)

        assert (
            "audience" in str(exc_info.value).lower()
            or "validation" in str(exc_info.value).lower()
            or "sso" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_callback_validates_signature(self, sso_service, saml_provider, mock_redis, valid_saml_attributes):
        """Invalid XML signature raises validation error."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.return_value = stored

        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_saml_attributes) as mock_parse:
            mock_parse.side_effect = Exception("Signature validation failed")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response-xml", request_id)

        assert (
            "signature" in str(exc_info.value).lower()
            or "validation" in str(exc_info.value).lower()
            or "saml" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_callback_validates_not_before_timestamp(
        self, sso_service, saml_provider, mock_redis, valid_saml_attributes
    ):
        """Assertion with future NotBefore is rejected."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.return_value = stored

        valid_saml_attributes["not_before"] = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_saml_attributes):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response-xml", request_id)

        assert (
            "timestamp" in str(exc_info.value).lower()
            or "expir" in str(exc_info.value).lower()
            or "validation" in str(exc_info.value).lower()
            or "saml" in str(exc_info.value).lower()
            or "not yet" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_callback_validates_not_on_or_after_timestamp(
        self, sso_service, saml_provider, mock_redis, valid_saml_attributes
    ):
        """Expired assertion (past NotOnOrAfter) is rejected."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.return_value = stored

        valid_saml_attributes["not_on_or_after"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_saml_attributes):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response-xml", request_id)

        assert (
            "timestamp" in str(exc_info.value).lower()
            or "expir" in str(exc_info.value).lower()
            or "validation" in str(exc_info.value).lower()
            or "saml" in str(exc_info.value).lower()
            or "not yet" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_callback_replay_protection_assertion_id_cache(
        self, sso_service, saml_provider, mock_redis, valid_saml_attributes
    ):
        """Assertion ID is cached in Redis to prevent replay."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]  # request lookup, assertion ID check

        valid_saml_attributes["assertion_id"] = "assertion-123"
        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_saml_attributes):
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = ({"user_id": "uuid"}, "session-id")
                await sso_service.process_saml_callback(saml_provider, "saml-response-xml", request_id)

        # Assertion ID should be cached
        call_found = False
        for call in mock_redis.set.call_args_list:
            args, kwargs = call
            if args[0] == "sso:saml:assertion:assertion-123":
                stored_value = json.loads(args[1])
                assert abs(stored_value["consumed_at"] - datetime.now(UTC).timestamp()) < 60
                assert abs(kwargs.get("ex", 0) - 28800) < 10
                call_found = True
                break
        assert call_found

    @pytest.mark.asyncio
    async def test_callback_rejects_replayed_assertion(
        self, sso_service, saml_provider, mock_redis, valid_saml_attributes
    ):
        """Reusing same assertion ID is rejected (replay protection)."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, "already-consumed"]  # request lookup, assertion ID already exists

        valid_saml_attributes["assertion_id"] = "assertion-123"
        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_saml_attributes):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response-xml", request_id)

        assert (
            "replay" in str(exc_info.value).lower()
            or "assertion" in str(exc_info.value).lower()
            or "validation" in str(exc_info.value).lower()
            or "saml" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_callback_validates_request_id_lookup(
        self, sso_service, saml_provider, mock_redis, valid_saml_attributes
    ):
        """Request ID must exist in Redis; missing request raises error."""
        mock_redis.get.return_value = None

        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_saml_attributes):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-response-xml", "missing-request")

        assert (
            "request" in str(exc_info.value).lower()
            or "session" in str(exc_info.value).lower()
            or "expir" in str(exc_info.value).lower()
            or "saml" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_callback_extracts_groups_from_attributes(
        self, sso_service, saml_provider, mock_redis, valid_saml_attributes
    ):
        """Groups attribute is extracted from assertion for role resolution."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_saml_attributes):
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = ({"user_id": "uuid"}, "session-id")
                await sso_service.process_saml_callback(saml_provider, "saml-response-xml", request_id)

        mock_resolve.assert_called_once()
        call_kwargs = mock_resolve.call_args[1]
        assert call_kwargs["groups"] == ["analysts", "data-team"]
        assert call_kwargs["email"] == "user@example.com"
        assert call_kwargs["subject_id"] == "user-subject-123"

    @pytest.mark.asyncio
    async def test_callback_returns_session_on_success(
        self, sso_service, saml_provider, mock_redis, valid_saml_attributes
    ):
        """Successful callback returns user profile and session ID."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        expected_profile = {
            "user_id": "user-uuid",
            "username": "user@example.com",
            "display_name": "user@example.com",
            "role_id": "role-uuid",
            "role_name": "Analyst",
            "permissions": ["query.submit", "query.history.view"],
            "auth_provider": "saml",
            "subject_id": "user-subject-123",
        }

        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_saml_attributes):
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = (expected_profile, "session-id-123")
                profile, session_id = await sso_service.process_saml_callback(
                    saml_provider, "saml-response-xml", request_id
                )

        assert profile["user_id"] == "user-uuid"
        assert profile["auth_provider"] == "saml"
        assert session_id == "session-id-123"

    @pytest.mark.asyncio
    async def test_callback_sanitized_error_no_raw_assertion(
        self, sso_service, saml_provider, mock_redis, valid_saml_attributes
    ):
        """Error response must not contain raw SAMLResponse or assertion XML."""
        request_id = "test-request-id"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.return_value = stored

        valid_saml_attributes["issuer"] = "https://evil.com"
        with patch.object(sso_service, "_parse_saml_assertion", return_value=valid_saml_attributes):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "raw-saml-response-xml", request_id)

        error_str = str(exc_info.value)
        assert "raw-saml-response-xml" not in error_str
        assert "user-subject-123" not in error_str
        assert "user@example.com" not in error_str
        assert "https://idp.example.com" not in error_str
