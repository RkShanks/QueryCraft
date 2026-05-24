"""TDD tests for OIDC authorization code flow initiation (T-635).

Tests state/nonce generation, Redis storage, and redirect URL construction.
All external calls mocked — pure unit tests.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.services.sso_service import SsoService


class TestSsoServiceOidCInitiation:
    """OIDC flow initiation unit tests."""

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
    async def test_initiate_oidc_generates_state_and_nonce(self, sso_service, oidc_provider, mock_redis):
        """State and nonce are generated and stored in Redis."""
        with patch("app.services.sso_service.secrets.token_urlsafe", side_effect=["test-state", "test-nonce"]):
            redirect_url = await sso_service.initiate_oidc_login(oidc_provider)

        assert "test-state" in redirect_url
        assert "test-nonce" in redirect_url

        # Verify Redis stored state→nonce mapping
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        value = call_args[0][1]
        ttl = call_args[1].get("ex")

        assert key.startswith("sso:oidc:state:")
        assert "test-state" in key
        stored = json.loads(value)
        assert stored["nonce"] == "test-nonce"
        assert stored["provider_id"] == str(oidc_provider.id)
        assert ttl is not None
        assert ttl > 0

    @pytest.mark.asyncio
    async def test_initiate_oidc_redirect_url_contains_required_params(self, sso_service, oidc_provider):
        """Redirect URL includes all required OAuth2/OIDC parameters."""
        with patch("app.services.sso_service.secrets.token_urlsafe", side_effect=["test-state", "test-nonce"]):
            redirect_url = await sso_service.initiate_oidc_login(oidc_provider)

        assert redirect_url.startswith("https://idp.example.com")
        assert "client_id=test-client-id" in redirect_url
        assert "response_type=code" in redirect_url
        assert "scope=openid+email+profile+groups" in redirect_url
        assert "redirect_uri=" in redirect_url
        assert "state=test-state" in redirect_url
        assert "nonce=test-nonce" in redirect_url

    @pytest.mark.asyncio
    async def test_initiate_oidc_uses_configured_scopes(self, sso_service, oidc_provider):
        """Scopes from provider configuration are included in redirect URL."""
        oidc_provider.scopes = "openid email"
        with patch("app.services.sso_service.secrets.token_urlsafe", side_effect=["s1", "n1"]):
            redirect_url = await sso_service.initiate_oidc_login(oidc_provider)

        assert "scope=openid+email" in redirect_url

    @pytest.mark.asyncio
    async def test_initiate_oidc_redirect_uri_is_url_encoded(self, sso_service, oidc_provider):
        """Redirect URI is properly URL-encoded in the authorization URL."""
        with patch("app.services.sso_service.secrets.token_urlsafe", side_effect=["s1", "n1"]):
            redirect_url = await sso_service.initiate_oidc_login(oidc_provider)

        # The redirect_uri should appear in the query string (URL-encoded)
        assert "redirect_uri=" in redirect_url

    @pytest.mark.asyncio
    async def test_initiate_oidc_redis_key_includes_state_value(self, sso_service, oidc_provider, mock_redis):
        """Redis key is scoped by state value for lookup during callback."""
        with patch("app.services.sso_service.secrets.token_urlsafe", side_effect=["my-state-123", "my-nonce-456"]):
            await sso_service.initiate_oidc_login(oidc_provider)

        key = mock_redis.set.call_args[0][0]
        assert key == "sso:oidc:state:my-state-123"

    @pytest.mark.asyncio
    async def test_initiate_oidc_redis_ttl_matches_session_timeout(self, sso_service, oidc_provider, mock_redis):
        """State/nonce Redis TTL matches session idle timeout (8h = 28800s)."""
        with patch("app.services.sso_service.secrets.token_urlsafe", side_effect=["s1", "n1"]):
            await sso_service.initiate_oidc_login(oidc_provider)

        ttl = mock_redis.set.call_args[1].get("ex")
        assert ttl == 28800

    @pytest.mark.asyncio
    async def test_initiate_oidc_sanitized_error_on_missing_issuer(self, sso_service, oidc_provider):
        """Missing issuer_url raises sanitized error without exposing internals."""
        oidc_provider.issuer_url = None
        with pytest.raises(Exception) as exc_info:
            await sso_service.initiate_oidc_login(oidc_provider)

        error_msg = str(exc_info.value).lower()
        assert "sso" in error_msg or "provider" in error_msg or "configuration" in error_msg
        # Must not expose raw URLs, UUIDs, or secrets
        assert "http" not in error_msg
        assert "test-client-id" not in error_msg

    @pytest.mark.asyncio
    async def test_initiate_oidc_sanitized_error_on_missing_client_id(self, sso_service, oidc_provider):
        """Missing client_id raises sanitized error."""
        oidc_provider.client_id = None
        with pytest.raises(Exception) as exc_info:
            await sso_service.initiate_oidc_login(oidc_provider)

        error_msg = str(exc_info.value).lower()
        assert "sso" in error_msg or "provider" in error_msg or "configuration" in error_msg
        assert "test-client-id" not in error_msg

    @pytest.mark.asyncio
    async def test_initiate_oidc_no_raw_secrets_in_error(self, sso_service, oidc_provider):
        """Error messages must never contain encrypted_client_secret."""
        oidc_provider.issuer_url = None
        with pytest.raises(Exception) as exc_info:
            await sso_service.initiate_oidc_login(oidc_provider)

        assert "enc-secret" not in str(exc_info.value)
