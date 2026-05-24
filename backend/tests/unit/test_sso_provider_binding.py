"""TDD tests for provider/state binding (PR-105 fix).

Tests that OIDC state and SAML request ID are bound to the provider
that initiated them. Callback with mismatched provider is rejected.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.services.sso_service import SsoService


class TestSsoProviderBinding:
    """Provider/state binding unit tests."""

    @pytest.fixture
    def provider_a(self):
        """Provider A."""
        p = MagicMock(spec=SsoProvider)
        p.id = "provider-a-uuid"
        p.protocol = SsoProtocol.OIDC
        p.display_name = "Provider A"
        p.issuer_url = "https://idp-a.example.com"
        p.client_id = "client-a"
        p.encrypted_client_secret = "enc-a"
        p.scopes = "openid email"
        p.redirect_uri = "https://app.example.com/callback"
        p.group_claim_name = "groups"
        return p

    @pytest.fixture
    def provider_b(self):
        """Provider B (different provider)."""
        p = MagicMock(spec=SsoProvider)
        p.id = "provider-b-uuid"
        p.protocol = SsoProtocol.OIDC
        p.display_name = "Provider B"
        p.issuer_url = "https://idp-b.example.com"
        p.client_id = "client-b"
        p.encrypted_client_secret = "enc-b"
        p.scopes = "openid email"
        p.redirect_uri = "https://app.example.com/callback"
        p.group_claim_name = "groups"
        return p

    @pytest.fixture
    def saml_provider_a(self):
        """SAML Provider A."""
        p = MagicMock(spec=SsoProvider)
        p.id = "saml-provider-a-uuid"
        p.protocol = SsoProtocol.SAML
        p.display_name = "SAML Provider A"
        p.saml_entity_id = "https://app.example.com/sp"
        p.saml_metadata_url = "https://idp-a.example.com/metadata"
        p.encrypted_saml_certificate = "enc-cert-a"
        p.group_claim_name = "groups"
        return p

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

    @pytest.mark.asyncio
    async def test_oidc_callback_rejects_provider_mismatch(self, sso_service, provider_a, provider_b, mock_redis):
        """OIDC callback with state from provider A but called with provider B is rejected."""
        state = "test-state"
        # State was stored for provider A
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(provider_a.id)})
        mock_redis.get.return_value = stored

        now = datetime.now(UTC)
        claims = {
            "iss": provider_b.issuer_url,
            "sub": "u1",
            "aud": provider_b.client_id,
            "exp": (now + timedelta(hours=1)).timestamp(),
            "nonce": "test-nonce",
        }

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (claims, "at")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(provider_b, state, "code")

        # Should fail because stored provider_id != callback provider.id
        assert (
            "provider" in str(exc_info.value).lower()
            or "mismatch" in str(exc_info.value).lower()
            or "session" in str(exc_info.value).lower()
            or "validation" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_oidc_callback_accepts_matching_provider(self, sso_service, provider_a, mock_redis):
        """OIDC callback with state from same provider passes."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(provider_a.id)})
        mock_redis.get.return_value = stored

        now = datetime.now(UTC)
        claims = {
            "iss": provider_a.issuer_url,
            "sub": "u1",
            "aud": provider_a.client_id,
            "exp": (now + timedelta(hours=1)).timestamp(),
            "nonce": "test-nonce",
        }

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (claims, "at")
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = ({"user_id": "uuid"}, "session-id")
                await sso_service.process_oidc_callback(provider_a, state, "code")

        mock_resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_saml_callback_rejects_provider_mismatch(self, sso_service, saml_provider_a, mock_redis):
        """SAML callback with request ID from provider A but different provider object is rejected."""
        request_id = "req-1"
        # Request stored for provider A
        stored = json.dumps({"provider_id": str(saml_provider_a.id)})
        mock_redis.get.return_value = stored

        # Create a different provider with same config but different ID
        provider_b = MagicMock(spec=SsoProvider)
        provider_b.id = "different-uuid"
        provider_b.protocol = SsoProtocol.SAML
        provider_b.saml_entity_id = saml_provider_a.saml_entity_id
        provider_b.saml_metadata_url = saml_provider_a.saml_metadata_url
        provider_b.encrypted_saml_certificate = saml_provider_a.encrypted_saml_certificate
        provider_b.group_claim_name = "groups"

        now = datetime.now(UTC)
        attrs = {
            "subject_id": "u1",
            "email": "u@example.com",
            "groups": ["analysts"],
            "issuer": "https://idp-a.example.com",
            "audience": "https://app.example.com/sp",
            "not_before": (now - timedelta(hours=1)).isoformat(),
            "not_on_or_after": (now + timedelta(hours=1)).isoformat(),
            "assertion_id": "assertion-1",
            "has_signature": True,
        }

        with patch.object(sso_service, "_parse_saml_assertion", return_value=attrs):
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_saml_callback(provider_b, "saml-response", request_id)

        assert (
            "provider" in str(exc_info.value).lower()
            or "mismatch" in str(exc_info.value).lower()
            or "session" in str(exc_info.value).lower()
            or "validation" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_saml_callback_accepts_matching_provider(self, sso_service, saml_provider_a, mock_redis):
        """SAML callback with request ID from same provider passes."""
        request_id = "req-1"
        stored = json.dumps({"provider_id": str(saml_provider_a.id)})
        mock_redis.get.side_effect = [stored, None]

        now = datetime.now(UTC)
        attrs = {
            "subject_id": "u1",
            "email": "u@example.com",
            "groups": ["analysts"],
            "issuer": "https://idp-a.example.com",
            "audience": "https://app.example.com/sp",
            "not_before": (now - timedelta(hours=1)).isoformat(),
            "not_on_or_after": (now + timedelta(hours=1)).isoformat(),
            "assertion_id": "assertion-1",
            "has_signature": True,
        }

        with patch.object(sso_service, "_parse_saml_assertion", return_value=attrs):
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = ({"user_id": "uuid"}, "session-id")
                await sso_service.process_saml_callback(saml_provider_a, "saml-response", request_id)

        mock_resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_oidc_stored_provider_id_matches_initiator(self, sso_service, provider_a, mock_redis):
        """initiate_oidc_login stores the correct provider_id in Redis."""
        with patch("app.services.sso_service.secrets.token_urlsafe", side_effect=["s1", "n1"]):
            await sso_service.initiate_oidc_login(provider_a)

        call_args = mock_redis.set.call_args
        stored = json.loads(call_args[0][1])
        assert stored["provider_id"] == str(provider_a.id)

    @pytest.mark.asyncio
    async def test_saml_stored_provider_id_matches_initiator(self, sso_service, saml_provider_a, mock_redis):
        """initiate_saml_login stores the correct provider_id in Redis."""
        with patch("app.services.sso_service.secrets.token_urlsafe", return_value="req-id"):
            with patch.object(sso_service, "_build_saml_authn_request", return_value="<AuthnRequest>"):
                await sso_service.initiate_saml_login(saml_provider_a)

        call_args = mock_redis.set.call_args
        stored = json.loads(call_args[0][1])
        assert stored["provider_id"] == str(saml_provider_a.id)
