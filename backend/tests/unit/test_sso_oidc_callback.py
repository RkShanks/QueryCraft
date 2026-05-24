"""TDD tests for OIDC callback validation (T-636).

Tests ID token validation per S-001: issuer, audience, signature, expiry,
nonce, state, replay protection. All external calls mocked.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.services.sso_service import SsoService


class TestSsoServiceOidCCallback:
    """OIDC callback validation unit tests."""

    @pytest.fixture
    def oidc_provider(self):
        """A configured OIDC provider."""
        provider = MagicMock(spec=SsoProvider)
        provider.id = "provider-oidc-uuid"
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
    def valid_id_token_claims(self):
        """Valid ID token claims for a successful callback."""
        now = datetime.now(UTC)
        return {
            "iss": "https://idp.example.com",
            "sub": "user-subject-123",
            "aud": "test-client-id",
            "exp": (now + timedelta(hours=1)).timestamp(),
            "iat": now.timestamp(),
            "nonce": "test-nonce",
            "email": "user@example.com",
            "groups": ["analysts", "data-team"],
        }

    @pytest.mark.asyncio
    async def test_callback_validates_issuer_matches_configured(
        self, sso_service, oidc_provider, mock_redis, valid_id_token_claims
    ):
        """ID token issuer must match configured issuer_url."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        valid_id_token_claims["iss"] = "https://evil.com"
        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (valid_id_token_claims, "access-token-123")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        assert "issuer" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_callback_validates_audience_contains_client_id(
        self, sso_service, oidc_provider, mock_redis, valid_id_token_claims
    ):
        """ID token audience must contain configured client_id."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        valid_id_token_claims["aud"] = "wrong-client-id"
        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (valid_id_token_claims, "access-token-123")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        assert "audience" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_callback_validates_expiry(self, sso_service, oidc_provider, mock_redis, valid_id_token_claims):
        """Expired ID token is rejected."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        valid_id_token_claims["exp"] = (datetime.now(UTC) - timedelta(hours=1)).timestamp()
        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (valid_id_token_claims, "access-token-123")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        assert "expir" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_callback_validates_nonce_matches_stored(
        self, sso_service, oidc_provider, mock_redis, valid_id_token_claims
    ):
        """ID token nonce must match Redis-stored nonce."""
        state = "test-state"
        stored = json.dumps({"nonce": "stored-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        valid_id_token_claims["nonce"] = "different-nonce"
        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (valid_id_token_claims, "access-token-123")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        assert "nonce" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_callback_validates_state_lookup(self, sso_service, oidc_provider, mock_redis, valid_id_token_claims):
        """State must exist in Redis; missing state raises error."""
        mock_redis.get.return_value = None

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (valid_id_token_claims, "access-token-123")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, "missing-state", "auth-code")

        assert (
            "state" in str(exc_info.value).lower()
            or "session" in str(exc_info.value).lower()
            or "expir" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_callback_consumes_nonce_replay_protection(
        self, sso_service, oidc_provider, mock_redis, valid_id_token_claims
    ):
        """After successful validation, nonce/state is deleted from Redis (replay protection)."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (valid_id_token_claims, "access-token-123")
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = ({"user_id": "uuid"}, "session-id")
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        mock_redis.delete.assert_called_with("sso:oidc:state:test-state")

    @pytest.mark.asyncio
    async def test_callback_rejects_replayed_state(self, sso_service, oidc_provider, mock_redis, valid_id_token_claims):
        """Reusing a consumed state raises error (replay protection)."""
        state = "test-state"
        mock_redis.get.return_value = None  # Already deleted

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (valid_id_token_claims, "access-token-123")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        assert (
            "state" in str(exc_info.value).lower()
            or "session" in str(exc_info.value).lower()
            or "expir" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_callback_allows_clock_skew_tolerance(
        self, sso_service, oidc_provider, mock_redis, valid_id_token_claims
    ):
        """Token exp within 30-second clock skew tolerance is accepted."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        # Token expired 15 seconds ago (within 30s tolerance)
        valid_id_token_claims["exp"] = (datetime.now(UTC) - timedelta(seconds=15)).timestamp()

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (valid_id_token_claims, "access-token-123")
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = ({"user_id": "uuid"}, "session-id")
                result = await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        assert result is not None

    @pytest.mark.asyncio
    async def test_callback_validates_signature(self, sso_service, oidc_provider, mock_redis, valid_id_token_claims):
        """Invalid signature raises validation error."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.side_effect = Exception("signature verification failed")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        assert (
            "signature" in str(exc_info.value).lower()
            or "validation" in str(exc_info.value).lower()
            or "sso" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_callback_extracts_groups_from_claim(
        self, sso_service, oidc_provider, mock_redis, valid_id_token_claims
    ):
        """Groups claim is extracted from ID token for role resolution."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (valid_id_token_claims, "access-token-123")
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = ({"user_id": "uuid"}, "session-id")
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        mock_resolve.assert_called_once()
        call_kwargs = mock_resolve.call_args[1]
        assert call_kwargs["groups"] == ["analysts", "data-team"]
        assert call_kwargs["email"] == "user@example.com"
        assert call_kwargs["subject_id"] == "user-subject-123"

    @pytest.mark.asyncio
    async def test_callback_returns_session_on_success(
        self, sso_service, oidc_provider, mock_redis, valid_id_token_claims
    ):
        """Successful callback returns user profile and session ID."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        expected_profile = {
            "user_id": "user-uuid",
            "username": "user@example.com",
            "display_name": "user@example.com",
            "role_id": "role-uuid",
            "role_name": "Analyst",
            "permissions": ["query.submit", "query.history.view"],
            "auth_provider": "oidc",
            "subject_id": "user-subject-123",
        }

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (valid_id_token_claims, "access-token-123")
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = (expected_profile, "session-id-123")
                profile, session_id = await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        assert profile["user_id"] == "user-uuid"
        assert profile["auth_provider"] == "oidc"
        assert session_id == "session-id-123"

    @pytest.mark.asyncio
    async def test_callback_sanitized_error_no_raw_token(
        self, sso_service, oidc_provider, mock_redis, valid_id_token_claims
    ):
        """Error response must not contain raw ID token or access token."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        valid_id_token_claims["iss"] = "https://evil.com"
        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (valid_id_token_claims, "access-token-123")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        error_str = str(exc_info.value)
        assert "access-token-123" not in error_str
        assert "user-subject-123" not in error_str
        assert "user@example.com" not in error_str
