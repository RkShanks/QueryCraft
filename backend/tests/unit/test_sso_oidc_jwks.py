"""TDD tests for OIDC JWKS signature validation (PR-105 fix).

Tests explicit JWKS fetch, signature validation against JWK, unknown kid,
wrong issuer/audience. All external HTTP calls mocked via respx.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from httpx import Response

from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider
from app.services.sso_service import SsoService


class TestSsoServiceOidCJwks:
    """OIDC JWKS/signature validation unit tests."""

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

    def _make_id_token(self, claims: dict, kid: str = "key-1") -> str:
        """Build an unsigned JWT-like token for JWKS tests.

        We mock the JWKS endpoint and the actual signature verification
        by patching jwt.decode to succeed/fail as needed. The important
        thing is that the code *fetches* the JWKS and passes it to decode.
        """
        import base64

        header = (
            base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT", "kid": kid}).encode())
            .decode()
            .rstrip("=")
        )
        payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        return f"{header}.{payload}.signature"

    @pytest.mark.asyncio
    async def test_exchange_fetches_jwks_and_decodes(self, sso_service, oidc_provider, mock_redis):
        """_exchange_code_for_token fetches JWKS from well-known endpoint."""
        with respx.mock:
            token_route = respx.post("https://idp.example.com/token").mock(
                return_value=Response(200, json={"id_token": "dummy", "access_token": "at"})
            )
            jwks_route = respx.get("https://idp.example.com/.well-known/jwks.json").mock(
                return_value=Response(200, json={"keys": [{"kid": "key-1", "kty": "RSA"}]})
            )

            with patch("authlib.jose.jwt") as mock_jwt:
                mock_claims = MagicMock()
                mock_claims.validate = MagicMock()
                mock_claims.__iter__ = MagicMock(return_value=iter({"sub": "u1"}.items()))
                mock_jwt.decode.return_value = mock_claims

                with patch("app.services.sso_service.decrypt", return_value="secret"):
                    claims, at = await sso_service._exchange_code_for_token(oidc_provider, "code")

            assert token_route.called
            assert jwks_route.called
            # jwt.decode should be called with the JWKS dict, not a URL string
            call_args = mock_jwt.decode.call_args
            assert call_args[0][0] == "dummy"
            # Second arg should be a dict (JWKS), not a string
            jwks_arg = call_args[0][1]
            assert isinstance(jwks_arg, dict)
            assert jwks_arg == {"keys": [{"kid": "key-1", "kty": "RSA"}]}

    @pytest.mark.asyncio
    async def test_jwks_fetch_failure_raises_sanitized(self, sso_service, oidc_provider):
        """JWKS endpoint returning 500 raises sanitized error."""
        with respx.mock:
            respx.post("https://idp.example.com/token").mock(
                return_value=Response(200, json={"id_token": "dummy", "access_token": "at"})
            )
            respx.get("https://idp.example.com/.well-known/jwks.json").mock(return_value=Response(500))

            with patch("app.services.sso_service.decrypt", return_value="secret"):
                with pytest.raises(Exception) as exc_info:
                    await sso_service._exchange_code_for_token(oidc_provider, "code")

            error = str(exc_info.value).lower()
            assert "sso" in error or "validation" in error or "token" in error
            assert "https://" not in str(exc_info.value)
            assert "idp.example.com" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_bad_signature_raises_sanitized(self, sso_service, oidc_provider):
        """jwt.decode raising InvalidTokenError becomes sanitized SsoValidationError."""
        with respx.mock:
            respx.post("https://idp.example.com/token").mock(
                return_value=Response(200, json={"id_token": "dummy", "access_token": "at"})
            )
            respx.get("https://idp.example.com/.well-known/jwks.json").mock(
                return_value=Response(200, json={"keys": [{"kid": "key-1", "kty": "RSA"}]})
            )

            from authlib.jose.errors import InvalidTokenError

            with patch("authlib.jose.jwt") as mock_jwt:
                mock_jwt.decode.side_effect = InvalidTokenError("bad signature")

                with patch("app.services.sso_service.decrypt", return_value="secret"):
                    with pytest.raises(Exception) as exc_info:
                        await sso_service._exchange_code_for_token(oidc_provider, "code")

            error = str(exc_info.value).lower()
            assert "signature" in error or "validation" in error or "sso" in error

    @pytest.mark.asyncio
    async def test_unknown_kid_raises_sanitized(self, sso_service, oidc_provider):
        """Token with kid not in JWKS raises sanitized error."""
        with respx.mock:
            respx.post("https://idp.example.com/token").mock(
                return_value=Response(200, json={"id_token": "dummy", "access_token": "at"})
            )
            respx.get("https://idp.example.com/.well-known/jwks.json").mock(
                return_value=Response(200, json={"keys": [{"kid": "other-key", "kty": "RSA"}]})
            )

            from authlib.jose.errors import InvalidTokenError

            with patch("authlib.jose.jwt") as mock_jwt:
                mock_jwt.decode.side_effect = InvalidTokenError("unknown kid")

                with patch("app.services.sso_service.decrypt", return_value="secret"):
                    with pytest.raises(Exception) as exc_info:
                        await sso_service._exchange_code_for_token(oidc_provider, "code")

            error = str(exc_info.value).lower()
            assert "signature" in error or "validation" in error or "sso" in error

    @pytest.mark.asyncio
    async def test_validate_claims_rejects_wrong_issuer(self, sso_service, oidc_provider):
        """ID token with wrong iss is rejected."""
        now = datetime.now(UTC)
        claims = {
            "iss": "https://evil.com",
            "sub": "u1",
            "aud": "test-client-id",
            "exp": (now + timedelta(hours=1)).timestamp(),
            "nonce": "n1",
        }
        with pytest.raises(Exception) as exc_info:
            sso_service._validate_oidc_claims(claims, oidc_provider, "n1")

        assert "issuer" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_claims_rejects_wrong_audience(self, sso_service, oidc_provider):
        """ID token with wrong aud is rejected."""
        now = datetime.now(UTC)
        claims = {
            "iss": "https://idp.example.com",
            "sub": "u1",
            "aud": "wrong-client",
            "exp": (now + timedelta(hours=1)).timestamp(),
            "nonce": "n1",
        }
        with pytest.raises(Exception) as exc_info:
            sso_service._validate_oidc_claims(claims, oidc_provider, "n1")

        assert "audience" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_claims_accepts_correct_issuer_aud(self, sso_service, oidc_provider):
        """Valid issuer and audience pass."""
        now = datetime.now(UTC)
        claims = {
            "iss": "https://idp.example.com",
            "sub": "u1",
            "aud": "test-client-id",
            "exp": (now + timedelta(hours=1)).timestamp(),
            "nonce": "n1",
        }
        # Should not raise
        sso_service._validate_oidc_claims(claims, oidc_provider, "n1")

    @pytest.mark.asyncio
    async def test_no_raw_token_in_error(self, sso_service, oidc_provider):
        """Error from _exchange_code_for_token must not contain raw id_token."""
        with respx.mock:
            respx.post("https://idp.example.com/token").mock(
                return_value=Response(200, json={"id_token": "secret-token-xyz", "access_token": "at"})
            )
            respx.get("https://idp.example.com/.well-known/jwks.json").mock(return_value=Response(500))

            with patch("app.services.sso_service.decrypt", return_value="secret"):
                with pytest.raises(Exception) as exc_info:
                    await sso_service._exchange_code_for_token(oidc_provider, "code")

            assert "secret-token-xyz" not in str(exc_info.value)
            assert "access_token" not in str(exc_info.value).lower()
