"""TDD tests for OIDC error cases (T-637).

Tests expired token, bad signature, wrong audience, missing nonce, replayed nonce.
All errors must be sanitized (no raw tokens, UUIDs, hostnames, secrets).
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.services.sso_service import SsoService


class TestSsoServiceOidCErrors:
    """OIDC error case unit tests."""

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
    def base_claims(self):
        """Base valid claims — tests mutate specific fields."""
        now = datetime.now(UTC)
        return {
            "iss": "https://idp.example.com",
            "sub": "user-subject-123",
            "aud": "test-client-id",
            "exp": (now + timedelta(hours=1)).timestamp(),
            "iat": now.timestamp(),
            "nonce": "test-nonce",
            "email": "user@example.com",
            "groups": ["analysts"],
        }

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, sso_service, oidc_provider, mock_redis, base_claims):
        """Token expired more than 30 seconds ago is rejected."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        base_claims["exp"] = (datetime.now(UTC) - timedelta(minutes=5)).timestamp()

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (base_claims, "access-token")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        assert "expir" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_bad_signature_rejected(self, sso_service, oidc_provider, mock_redis, base_claims):
        """Signature verification failure raises sanitized error."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.side_effect = Exception("Invalid JWT signature")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        error = str(exc_info.value).lower()
        assert "signature" in error or "validation" in error or "sso" in error

    @pytest.mark.asyncio
    async def test_wrong_audience_rejected(self, sso_service, oidc_provider, mock_redis, base_claims):
        """Audience mismatch raises sanitized error."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        base_claims["aud"] = "wrong-client-id"

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (base_claims, "access-token")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        error = str(exc_info.value).lower()
        assert "audience" in error or "validation" in error or "sso" in error

    @pytest.mark.asyncio
    async def test_missing_nonce_rejected(self, sso_service, oidc_provider, mock_redis, base_claims):
        """ID token without nonce claim raises sanitized error."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        del base_claims["nonce"]

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (base_claims, "access-token")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        error = str(exc_info.value).lower()
        assert "nonce" in error or "validation" in error or "sso" in error

    @pytest.mark.asyncio
    async def test_replayed_nonce_rejected(self, sso_service, oidc_provider, mock_redis, base_claims):
        """Reusing a consumed state/nonce is rejected (replay protection)."""
        state = "test-state"
        # First call: state exists, gets consumed
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.side_effect = [stored, None]

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (base_claims, "access-token")
            with patch.object(sso_service, "_resolve_role_and_create_session", new_callable=AsyncMock) as mock_resolve:
                mock_resolve.return_value = ({"user_id": "uuid"}, "session-id")
                # First callback succeeds
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        # Second callback with same state fails
        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (base_claims, "access-token")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        error = str(exc_info.value).lower()
        assert "state" in error or "session" in error or "expir" in error or "sso" in error

    @pytest.mark.asyncio
    async def test_error_does_not_expose_raw_token(self, sso_service, oidc_provider, mock_redis, base_claims):
        """Error messages must never contain raw ID token, access token, or claims."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        base_claims["iss"] = "https://evil.com"

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (base_claims, "access-token-123")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        error_str = str(exc_info.value)
        assert "access-token-123" not in error_str
        assert "user-subject-123" not in error_str
        assert "user@example.com" not in error_str
        assert "https://idp.example.com" not in error_str
        assert "test-client-id" not in error_str

    @pytest.mark.asyncio
    async def test_error_does_not_expose_hostname(self, sso_service, oidc_provider, mock_redis, base_claims):
        """Error messages must not expose IdP hostname or URLs."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        base_claims["iss"] = "https://evil.com"

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (base_claims, "access-token")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        assert "https://" not in str(exc_info.value)
        assert "evil.com" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_does_not_expose_uuid(self, sso_service, oidc_provider, mock_redis, base_claims):
        """Error messages must not expose provider UUIDs."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        base_claims["iss"] = "https://evil.com"

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (base_claims, "access-token")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        assert "provider-oidc-uuid" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_does_not_expose_encrypted_secret(self, sso_service, oidc_provider, mock_redis, base_claims):
        """Error messages must not expose encrypted client secret."""
        state = "test-state"
        stored = json.dumps({"nonce": "test-nonce", "provider_id": str(oidc_provider.id)})
        mock_redis.get.return_value = stored

        base_claims["iss"] = "https://evil.com"

        with patch.object(sso_service, "_exchange_code_for_token", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = (base_claims, "access-token")
            with pytest.raises(Exception) as exc_info:
                await sso_service.process_oidc_callback(oidc_provider, state, "auth-code")

        assert "enc-secret" not in str(exc_info.value)
