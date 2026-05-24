"""TDD tests for replay protection — Redis nonce/assertion ID cache (T-644).

Focused tests verifying the Redis-based replay protection mechanism:
- OIDC state is consumed (deleted) on first callback use
- OIDC state cannot be reused after consumption
- SAML request ID is consumed on first callback use
- SAML request ID cannot be reused after consumption
- SAML assertion ID is cached in Redis with correct TTL
- SAML assertion ID replay is detected and rejected
- Cache TTL matches session idle timeout (28800s by default)
- Provider binding prevents cross-provider replay
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.services.sso_service import SsoService, SsoValidationError


class TestOidcReplayProtection:
    """OIDC state/nonce replay protection tests."""

    @pytest.fixture
    def oidc_provider(self):
        provider = MagicMock(spec=SsoProvider)
        provider.id = "oidc-provider-uuid"
        provider.protocol = SsoProtocol.OIDC
        provider.display_name = "Test OIDC"
        provider.issuer_url = "https://idp.example.com"
        provider.client_id = "test-client-id"
        provider.encrypted_client_secret = "enc-secret"
        provider.scopes = "openid email profile groups"
        provider.redirect_uri = "https://app.example.com/api/v1/auth/sso/oidc/callback"
        provider.group_claim_name = "groups"
        return provider

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def sso_service(self, mock_db, mock_redis):
        with patch("app.services.sso_service.get_settings") as mock_settings:
            settings = MagicMock()
            settings.PLATFORM_ENCRYPTION_KEY = "d1OQc28ErbKH8nnhjNbchX5y_1EyXcfclkK1hPjPqFY="
            settings.SESSION_IDLE_TIMEOUT_HOURS = 8
            settings.BASE_URL = "https://app.example.com"
            mock_settings.return_value = settings
            return SsoService(mock_db, mock_redis)

    @pytest.mark.asyncio
    async def test_oidc_state_stored_with_session_timeout_ttl(self, sso_service, oidc_provider, mock_redis):
        """OIDC state is stored in Redis with TTL = session idle timeout."""
        with patch("app.services.sso_service.secrets.token_urlsafe", side_effect=["state-1", "nonce-1"]):
            await sso_service.initiate_oidc_login(oidc_provider)

        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        ttl = call_args[1].get("ex")
        assert key == "sso:oidc:state:state-1"
        assert ttl == 28800

    @pytest.mark.asyncio
    async def test_oidc_state_consumed_on_callback(self, sso_service, oidc_provider, mock_redis):
        """OIDC state is deleted from Redis after first successful callback lookup."""
        state = "state-consumed"
        stored = json.dumps({"nonce": "nonce-1", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        claims = {
            "iss": oidc_provider.issuer_url,
            "sub": "user-1",
            "aud": oidc_provider.client_id,
            "exp": 9999999999,
            "nonce": "nonce-1",
            "email": "user@example.com",
            "groups": ["analysts"],
        }
        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (claims, "access-token")
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = ({"user_id": "u1"}, "session-id")
                await sso_service.process_oidc_callback(oidc_provider, state, "code-1")

        mock_redis.delete.assert_called_with("sso:oidc:state:state-consumed")

    @pytest.mark.asyncio
    async def test_oidc_state_replay_rejected(self, sso_service, oidc_provider, mock_redis):
        """Reusing a consumed OIDC state is rejected."""
        state = "state-replayed"
        mock_redis.get.return_value = None

        with pytest.raises(SsoValidationError) as exc_info:
            await sso_service.process_oidc_callback(oidc_provider, state, "code-1")

        assert "session" in str(exc_info.value).lower() or "expir" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_oidc_provider_binding_prevents_cross_provider_replay(self, sso_service, oidc_provider, mock_redis):
        """State bound to one provider cannot be used with a different provider."""
        state = "state-bound"
        other_provider = MagicMock(spec=SsoProvider)
        other_provider.id = "other-provider-uuid"
        other_provider.protocol = SsoProtocol.OIDC
        other_provider.display_name = "Other OIDC"
        other_provider.issuer_url = "https://other-idp.example.com"
        other_provider.client_id = "other-client-id"
        other_provider.encrypted_client_secret = "enc-other"
        other_provider.scopes = "openid"
        other_provider.redirect_uri = "https://app.example.com/other/callback"
        other_provider.group_claim_name = "groups"

        stored = json.dumps({"nonce": "nonce-1", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        with pytest.raises(SsoValidationError) as exc_info:
            await sso_service.process_oidc_callback(other_provider, state, "code-1")

        assert "mismatch" in str(exc_info.value).lower()


class TestSamlReplayProtection:
    """SAML request ID / assertion ID replay protection tests."""

    @pytest.fixture
    def saml_provider(self):
        provider = MagicMock(spec=SsoProvider)
        provider.id = "saml-provider-uuid"
        provider.protocol = SsoProtocol.SAML
        provider.display_name = "Test SAML"
        provider.saml_entity_id = "https://app.example.com/sp"
        provider.saml_metadata_url = "https://idp.example.com/metadata"
        provider.encrypted_saml_certificate = "enc-cert"
        provider.group_claim_name = "groups"
        return provider

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def sso_service(self, mock_db, mock_redis):
        with patch("app.services.sso_service.get_settings") as mock_settings:
            settings = MagicMock()
            settings.PLATFORM_ENCRYPTION_KEY = "d1OQc28ErbKH8nnhjNbchX5y_1EyXcfclkK1hPjPqFY="
            settings.SESSION_IDLE_TIMEOUT_HOURS = 8
            settings.BASE_URL = "https://app.example.com"
            mock_settings.return_value = settings
            return SsoService(mock_db, mock_redis)

    @pytest.mark.asyncio
    async def test_saml_request_id_stored_with_session_timeout_ttl(self, sso_service, saml_provider, mock_redis):
        """SAML request ID is stored in Redis with TTL = session idle timeout."""
        with patch("app.services.sso_service.secrets.token_urlsafe", return_value="req-id-1"):
            with patch.object(sso_service, "_build_saml_authn_request", return_value="<AuthnRequest/>"):
                with patch.object(sso_service, "_get_idp_sso_url", return_value="https://idp.example.com/sso"):
                    await sso_service.initiate_saml_login(saml_provider)

        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        ttl = call_args[1].get("ex")
        assert key == "sso:saml:request:req-id-1"
        assert ttl == 28800

    @pytest.mark.asyncio
    async def test_saml_request_id_consumed_on_callback(self, sso_service, saml_provider, mock_redis):
        """SAML request ID is deleted from Redis after first callback."""
        request_id = "req-id-consumed"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        attrs = {
            "subject_id": "user-1",
            "email": "user@example.com",
            "groups": ["analysts"],
            "issuer": "https://idp.example.com",
            "not_before": None,
            "not_on_or_after": None,
            "assertion_id": "assertion-1",
        }
        with patch.object(sso_service, "_parse_saml_assertion", return_value=attrs):
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = ({"user_id": "u1"}, "session-id")
                await sso_service.process_saml_callback(saml_provider, "saml-resp", request_id)

        mock_redis.delete.assert_called_with("sso:saml:request:req-id-consumed")

    @pytest.mark.asyncio
    async def test_saml_request_id_replay_rejected(self, sso_service, saml_provider, mock_redis):
        """Reusing a consumed SAML request ID is rejected."""
        request_id = "req-id-replayed"
        mock_redis.get.return_value = None

        with pytest.raises(SsoValidationError) as exc_info:
            await sso_service.process_saml_callback(saml_provider, "saml-resp", request_id)

        assert "session" in str(exc_info.value).lower() or "expir" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_saml_assertion_id_cached_with_correct_ttl(self, sso_service, saml_provider, mock_redis):
        """SAML assertion ID is cached in Redis with TTL = session idle timeout."""
        request_id = "req-id-1"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        attrs = {
            "subject_id": "user-1",
            "email": "user@example.com",
            "groups": ["analysts"],
            "issuer": "https://idp.example.com",
            "not_before": None,
            "not_on_or_after": None,
            "assertion_id": "assertion-unique-1",
        }
        with patch.object(sso_service, "_parse_saml_assertion", return_value=attrs):
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = ({"user_id": "u1"}, "session-id")
                await sso_service.process_saml_callback(saml_provider, "saml-resp", request_id)

        assertion_set_calls = [
            c for c in mock_redis.set.call_args_list if c[0][0] == "sso:saml:assertion:assertion-unique-1"
        ]
        assert len(assertion_set_calls) == 1
        call = assertion_set_calls[0]
        stored_value = json.loads(call[0][1])
        assert "consumed_at" in stored_value
        assert call[1].get("ex") == 28800

    @pytest.mark.asyncio
    async def test_saml_assertion_id_replay_rejected(self, sso_service, saml_provider, mock_redis):
        """Reusing same assertion ID within TTL is rejected (replay detected)."""
        request_id = "req-id-1"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, "already-consumed"]

        attrs = {
            "subject_id": "user-1",
            "email": "user@example.com",
            "groups": ["analysts"],
            "issuer": "https://idp.example.com",
            "not_before": None,
            "not_on_or_after": None,
            "assertion_id": "assertion-replayed",
        }
        with patch.object(sso_service, "_parse_saml_assertion", return_value=attrs):
            with pytest.raises(SsoValidationError) as exc_info:
                await sso_service.process_saml_callback(saml_provider, "saml-resp", request_id)

        assert "replay" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_saml_provider_binding_prevents_cross_provider_replay(self, sso_service, saml_provider, mock_redis):
        """Request ID bound to one provider cannot be used with a different provider."""
        request_id = "req-id-bound"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.return_value = stored

        other_provider = MagicMock(spec=SsoProvider)
        other_provider.id = "other-saml-uuid"
        other_provider.protocol = SsoProtocol.SAML
        other_provider.display_name = "Other SAML"
        other_provider.saml_entity_id = "https://other.example.com/sp"
        other_provider.saml_metadata_url = "https://other-idp.example.com/metadata"
        other_provider.encrypted_saml_certificate = "enc-other-cert"
        other_provider.group_claim_name = "groups"

        with pytest.raises(SsoValidationError) as exc_info:
            await sso_service.process_saml_callback(other_provider, "saml-resp", request_id)

        assert "mismatch" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_saml_assertion_without_id_still_succeeds(self, sso_service, saml_provider, mock_redis):
        """SAML assertion with no assertion_id skips replay cache but still succeeds."""
        request_id = "req-id-no-assert"
        stored = json.dumps({"provider_id": str(saml_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        attrs = {
            "subject_id": "user-1",
            "email": "user@example.com",
            "groups": ["analysts"],
            "issuer": "https://idp.example.com",
            "not_before": None,
            "not_on_or_after": None,
            "assertion_id": "",
        }
        with patch.object(sso_service, "_parse_saml_assertion", return_value=attrs):
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = ({"user_id": "u1"}, "session-id")
                profile, session_id = await sso_service.process_saml_callback(saml_provider, "saml-resp", request_id)

        assert profile is not None
        assert session_id == "session-id"
