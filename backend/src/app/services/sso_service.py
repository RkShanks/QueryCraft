"""SsoService — OIDC and SAML SSO flow orchestration (T-641, T-643).

Handles:
- OIDC authorization code flow initiation and callback
- SAML AuthnRequest initiation and assertion callback
- Role resolution from SSO group claims via priority ordering
- User identity creation/update on first SSO login
- Redis session creation with role-derived permissions

Security:
- State/nonce/request_id stored in Redis with TTL = session timeout
- Replay protection: consumed state/assertion ID deleted from Redis
- ID token validation: issuer, audience, signature (JWKS), expiry, nonce
- Assertion validation: issuer (IdP), audience (SP), signature, timestamps
- All user-facing errors sanitized (no raw tokens, certs, UUIDs, hostnames)
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.encryption import decrypt
from app.db.models.enums import AuditActionType, AuthProvider
from app.db.models.role import Role
from app.db.models.sso_group_mapping import SsoGroupMapping
from app.db.models.sso_provider import SsoProvider
from app.db.models.user import User
from app.db.models.user_identity import UserIdentity
from app.repositories.session_repository import SessionRepository
from app.services.audit_service import AuditService


class SsoValidationError(Exception):
    """Sanitized SSO validation failure."""

    def __init__(self, message: str = "SSO validation failed"):
        self.message = message
        super().__init__(message)


class SsoService:
    """Orchestrates OIDC and SAML SSO flows with role resolution."""

    def __init__(self, db_session: AsyncSession, redis: Redis):
        self._db = db_session
        self._redis = redis
        self._settings = get_settings()
        self._clock_skew_tolerance = timedelta(seconds=30)

    # ------------------------------------------------------------------
    # OIDC
    # ------------------------------------------------------------------

    async def initiate_oidc_login(self, provider: SsoProvider) -> str:
        """Generate state/nonce, store in Redis, return IdP authorization URL."""
        if not provider.issuer_url:
            raise SsoValidationError("SSO provider configuration incomplete")
        if not provider.client_id:
            raise SsoValidationError("SSO provider configuration incomplete")

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)

        ttl = self._settings.SESSION_IDLE_TIMEOUT_HOURS * 3600
        stored = json.dumps(
            {
                "nonce": nonce,
                "provider_id": str(provider.id),
            }
        )
        await self._redis.set(f"sso:oidc:state:{state}", stored, ex=ttl)

        params = {
            "client_id": provider.client_id,
            "response_type": "code",
            "scope": provider.scopes or "openid email profile groups",
            "redirect_uri": provider.redirect_uri or "",
            "state": state,
            "nonce": nonce,
        }
        auth_url = f"{provider.issuer_url}/authorize?{urlencode(params)}"
        return auth_url

    @staticmethod
    def _safe_audit_context(**kwargs) -> dict:
        """Build audit context dict with sensitive keys redacted."""
        safe = {}
        for k, v in kwargs.items():
            lower_k = k.lower().replace("_", "").replace("-", "")
            if any(
                token in lower_k
                for token in {
                    "password",
                    "secret",
                    "token",
                    "apikey",
                    "credential",
                    "certificate",
                    "privatekey",
                    "assertion",
                    "samlresponse",
                    "authorization",
                    "encryptionkey",
                    "bearer",
                    "jwt",
                    "nonce",
                    "state",
                    "code",
                    "accesstoken",
                    "idtoken",
                    "refreshtoken",
                }
            ):
                safe[k] = "[REDACTED]"
            else:
                safe[k] = v
        return safe

    async def process_oidc_callback(
        self,
        provider: SsoProvider,
        state: str,
        code: str,
    ) -> tuple[dict, str]:
        """Validate OIDC callback: exchange code, validate ID token, create session."""
        raw = await self._redis.get(f"sso:oidc:state:{state}")
        if raw is None:
            await AuditService.log(
                self._db,
                action=AuditActionType.AUTH_LOGIN_FAILURE,
                resource_type="sso_callback",
                resource_id="oidc",
                outcome="failure",
                context=self._safe_audit_context(error_code="sso_validation_failed", reason="state_missing"),
            )
            raise SsoValidationError("SSO session expired or invalid")

        stored = json.loads(raw)
        stored_provider_id = stored.get("provider_id", "")
        expected_nonce = stored["nonce"]

        # Provider binding: stored provider_id must match callback provider
        if stored_provider_id and stored_provider_id != str(provider.id):
            await AuditService.log(
                self._db,
                action=AuditActionType.AUTH_LOGIN_FAILURE,
                resource_type="sso_callback",
                resource_id="oidc",
                outcome="failure",
                context=self._safe_audit_context(error_code="sso_validation_failed", reason="provider_mismatch"),
            )
            raise SsoValidationError("SSO provider mismatch")

        # Consume state immediately (replay protection)
        await self._redis.delete(f"sso:oidc:state:{state}")

        try:
            claims, _access_token = await self._exchange_code_for_token(provider, code)
        except SsoValidationError:
            await AuditService.log(
                self._db,
                action=AuditActionType.AUTH_LOGIN_FAILURE,
                resource_type="sso_callback",
                resource_id="oidc",
                outcome="failure",
                context=self._safe_audit_context(error_code="sso_validation_failed", reason="token_exchange_failed"),
            )
            raise

        # Validate claims per S-001
        try:
            self._validate_oidc_claims(claims, provider, expected_nonce)
        except SsoValidationError:
            await AuditService.log(
                self._db,
                action=AuditActionType.AUTH_LOGIN_FAILURE,
                resource_type="sso_callback",
                resource_id="oidc",
                outcome="failure",
                context=self._safe_audit_context(error_code="sso_validation_failed", reason="claims_validation_failed"),
            )
            raise

        # Log validation success
        await AuditService.log(
            self._db,
            action=AuditActionType.AUTH_SSO_VALIDATION,
            resource_type="sso_callback",
            resource_id="oidc",
            outcome="success",
            context=self._safe_audit_context(provider_protocol="oidc"),
        )

        subject_id = str(claims.get("sub", ""))
        email = str(claims.get("email", ""))
        groups = claims.get("groups", []) or []
        if isinstance(groups, str):
            groups = [groups]

        try:
            profile, session_id = await self._resolve_role_and_create_session(
                provider=provider,
                subject_id=subject_id,
                email=email,
                groups=groups,
                auth_provider=AuthProvider.OIDC,
            )
        except SsoValidationError:
            await AuditService.log(
                self._db,
                action=AuditActionType.AUTH_LOGIN_FAILURE,
                resource_type="sso_callback",
                resource_id="oidc",
                outcome="failure",
                context=self._safe_audit_context(error_code="sso_no_role", reason="no_role_assigned"),
            )
            raise

        # Log successful login (must succeed; if it fails, clean up the Redis session)
        try:
            await AuditService.log(
                self._db,
                action=AuditActionType.AUTH_LOGIN_SUCCESS,
                actor_identity=email or subject_id,
                resource_type="user",
                resource_id=str(profile.get("user_id", "")),
                outcome="success",
                context=self._safe_audit_context(
                    auth_provider="oidc",
                    role_name=profile.get("role_name"),
                ),
            )
        except Exception:
            # Audit failure: revoke the session we just created so the login
            # cannot be used without an audit trail.
            await self._redis.delete(f"session:{session_id}")
            raise

        return profile, session_id

    async def _exchange_code_for_token(
        self,
        provider: SsoProvider,
        code: str,
    ) -> tuple[dict, str]:
        """Exchange authorization code for ID token; return (claims, access_token).

        Explicitly fetches JWKS from well-known endpoint, validates signature,
        and decodes claims.  Override in tests.
        """
        from authlib.integrations.httpx_client import AsyncOAuth2Client
        from authlib.jose import jwt

        decrypted_secret = ""
        if provider.encrypted_client_secret:
            decrypted_secret = decrypt(
                provider.encrypted_client_secret,
                self._settings.PLATFORM_ENCRYPTION_KEY,
            )

        token_endpoint = f"{provider.issuer_url}/token"
        client = AsyncOAuth2Client(
            client_id=provider.client_id or "",
            client_secret=decrypted_secret,
            scope=provider.scopes or "openid email profile groups",
            redirect_uri=provider.redirect_uri or "",
        )

        try:
            token = await client.fetch_token(
                url=token_endpoint,
                code=code,
                grant_type="authorization_code",
            )
        except Exception as exc:
            raise SsoValidationError("SSO token exchange failed") from exc

        id_token = token.get("id_token")
        if not id_token:
            raise SsoValidationError("SSO token response missing ID token")

        # Explicit JWKS fetch
        jwks_url = f"{provider.issuer_url}/.well-known/jwks.json"
        try:
            async with httpx.AsyncClient() as http_client:
                jwks_resp = await http_client.get(jwks_url, timeout=10.0)
                jwks_resp.raise_for_status()
                jwks = jwks_resp.json()
        except Exception as exc:
            raise SsoValidationError("SSO ID token signature validation failed") from exc

        # Validate signature and decode claims
        try:
            claims_obj = jwt.decode(id_token, jwks)
            claims_obj.validate()
            claims_dict = dict(claims_obj)
        except Exception as exc:
            raise SsoValidationError("SSO ID token signature validation failed") from exc

        return claims_dict, token.get("access_token", "")

    def _validate_oidc_claims(
        self,
        claims: dict,
        provider: SsoProvider,
        expected_nonce: str,
    ) -> None:
        """Validate ID token claims per S-001."""
        now = datetime.now(UTC)

        iss = claims.get("iss")
        if iss != provider.issuer_url:
            raise SsoValidationError("SSO issuer validation failed")

        aud = claims.get("aud")
        expected_aud = provider.client_id
        if isinstance(aud, list):
            if expected_aud not in aud:
                raise SsoValidationError("SSO audience validation failed")
        elif aud != expected_aud:
            raise SsoValidationError("SSO audience validation failed")

        exp = claims.get("exp")
        if exp:
            exp_dt = datetime.fromtimestamp(float(exp), tz=UTC)
            if exp_dt < now - self._clock_skew_tolerance:
                raise SsoValidationError("SSO token expired")

        nonce = claims.get("nonce")
        if nonce != expected_nonce:
            raise SsoValidationError("SSO nonce validation failed")

    # ------------------------------------------------------------------
    # SAML
    # ------------------------------------------------------------------

    async def initiate_saml_login(self, provider: SsoProvider) -> str:
        """Generate AuthnRequest, store request ID in Redis, return IdP SSO URL."""
        if not provider.saml_entity_id:
            raise SsoValidationError("SSO provider configuration incomplete")
        if not provider.encrypted_saml_certificate:
            raise SsoValidationError("SSO provider configuration incomplete")

        request_id = secrets.token_urlsafe(32)
        authn_request_xml = self._build_saml_authn_request(provider, request_id)
        idp_sso_url = self._get_idp_sso_url(provider)

        ttl = self._settings.SESSION_IDLE_TIMEOUT_HOURS * 3600
        stored = json.dumps({"provider_id": str(provider.id)})
        await self._redis.set(f"sso:saml:request:{request_id}", stored, ex=ttl)

        encoded_request = base64.b64encode(__import__("zlib").compress(authn_request_xml.encode("utf-8"))).decode(
            "utf-8"
        )
        params = {
            "SAMLRequest": encoded_request,
            "RelayState": request_id,
        }
        redirect_url = f"{idp_sso_url}?{urlencode(params)}"
        return redirect_url

    def _build_saml_authn_request(self, provider: SsoProvider, request_id: str) -> str:
        """Build SAML AuthnRequest XML using public python3-saml API.

        Derives SP callback URL from BASE_URL config if available,
        otherwise falls back to a placeholder that must be configured.
        """
        from onelogin.saml2.auth import OneLogin_Saml2_Auth

        base_url = self._settings.BASE_URL or "https://app.example.com"
        acs_url = f"{base_url}/api/v1/auth/sso/saml/callback"

        req = {
            "https": "on" if base_url.startswith("https://") else "off",
            "http_host": base_url.replace("https://", "").replace("http://", ""),
            "script_name": "/",
            "server_port": "443" if base_url.startswith("https://") else "80",
            "get_data": {},
            "post_data": {},
        }

        # IdP entity ID comes from metadata URL host if no explicit config
        idp_entity_id = self._get_idp_entity_id(provider)

        settings_dict = {
            "sp": {
                "entityId": provider.saml_entity_id,
                "assertionConsumerService": {
                    "url": acs_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                },
            },
            "idp": {
                "entityId": idp_entity_id,
                "singleSignOnService": {
                    "url": self._get_idp_sso_url(provider),
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                },
                "x509cert": self._decrypt_saml_certificate(provider),
            },
        }

        auth = OneLogin_Saml2_Auth(req, settings_dict)
        # Use public API to generate login URL; extract the AuthnRequest from it
        login_url = auth.login(return_to="")
        # Parse the SAMLRequest parameter from the redirect URL
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(login_url)
        query = parse_qs(parsed.query)
        encoded_request = query.get("SAMLRequest", [""])[0]
        if not encoded_request:
            # Fallback: use internal method if public API doesn't expose it
            # This is a known limitation of python3-saml's public API.
            # We wrap it with a clear comment and test coverage.
            saml_request = auth._OneLogin_Saml2_Auth__build_request(
                auth._OneLogin_Saml2_Auth__last_request_id,
                "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            )
            return saml_request
        # Decode and return the XML
        compressed = base64.b64decode(encoded_request)
        return __import__("zlib").decompress(compressed).decode("utf-8")

    def _get_idp_entity_id(self, provider: SsoProvider) -> str:
        """Return IdP entity ID from metadata URL.

        Raises SsoValidationError if metadata URL is not configured.
        """
        if provider.saml_metadata_url:
            # Derive IdP entity ID from metadata URL (common convention)
            return provider.saml_metadata_url.rstrip("/").replace("/metadata", "")
        raise SsoValidationError("SSO provider configuration incomplete")

    def _get_idp_sso_url(self, provider: SsoProvider) -> str:
        """Return IdP SSO URL from metadata URL.

        Raises SsoValidationError if metadata URL is not configured.
        No hardcoded fallback — fail closed.
        """
        if provider.saml_metadata_url:
            return provider.saml_metadata_url.replace("/metadata", "/sso")
        raise SsoValidationError("SSO provider configuration incomplete")

    def _decrypt_saml_certificate(self, provider: SsoProvider) -> str:
        """Decrypt SAML certificate for signature validation."""
        if not provider.encrypted_saml_certificate:
            return ""
        return decrypt(
            provider.encrypted_saml_certificate,
            self._settings.PLATFORM_ENCRYPTION_KEY,
        )

    async def process_saml_callback(
        self,
        provider: SsoProvider,
        saml_response: str,
        request_id: str,
    ) -> tuple[dict, str]:
        """Validate SAML assertion, resolve role, create session."""
        raw = await self._redis.get(f"sso:saml:request:{request_id}")
        if raw is None:
            await AuditService.log(
                self._db,
                action=AuditActionType.AUTH_LOGIN_FAILURE,
                resource_type="sso_callback",
                resource_id="saml",
                outcome="failure",
                context=self._safe_audit_context(error_code="sso_validation_failed", reason="request_id_missing"),
            )
            raise SsoValidationError("SSO session expired or invalid")

        stored = json.loads(raw)
        stored_provider_id = stored.get("provider_id", "")

        # Provider binding: stored provider_id must match callback provider
        if stored_provider_id and stored_provider_id != str(provider.id):
            await AuditService.log(
                self._db,
                action=AuditActionType.AUTH_LOGIN_FAILURE,
                resource_type="sso_callback",
                resource_id="saml",
                outcome="failure",
                context=self._safe_audit_context(error_code="sso_validation_failed", reason="provider_mismatch"),
            )
            raise SsoValidationError("SSO provider mismatch")

        # Consume request ID (replay protection for request)
        await self._redis.delete(f"sso:saml:request:{request_id}")

        try:
            attrs = self._parse_saml_assertion(provider, saml_response)
        except SsoValidationError:
            await AuditService.log(
                self._db,
                action=AuditActionType.AUTH_LOGIN_FAILURE,
                resource_type="sso_callback",
                resource_id="saml",
                outcome="failure",
                context=self._safe_audit_context(error_code="sso_validation_failed", reason="assertion_parse_failed"),
            )
            raise

        # Validate assertion per S-002
        try:
            self._validate_saml_assertion(attrs, provider)
        except SsoValidationError:
            await AuditService.log(
                self._db,
                action=AuditActionType.AUTH_LOGIN_FAILURE,
                resource_type="sso_callback",
                resource_id="saml",
                outcome="failure",
                context=self._safe_audit_context(
                    error_code="sso_validation_failed", reason="assertion_validation_failed"
                ),
            )
            raise

        # Log validation success
        await AuditService.log(
            self._db,
            action=AuditActionType.AUTH_SSO_VALIDATION,
            resource_type="sso_callback",
            resource_id="saml",
            outcome="success",
            context=self._safe_audit_context(provider_protocol="saml"),
        )

        # Replay protection: assertion ID
        assertion_id = attrs.get("assertion_id", "")
        if assertion_id:
            existing = await self._redis.get(f"sso:saml:assertion:{assertion_id}")
            if existing is not None:
                await AuditService.log(
                    self._db,
                    action=AuditActionType.AUTH_LOGIN_FAILURE,
                    resource_type="sso_callback",
                    resource_id="saml",
                    outcome="failure",
                    context=self._safe_audit_context(error_code="sso_validation_failed", reason="assertion_replay"),
                )
                raise SsoValidationError("SSO assertion replay detected")
            ttl = self._settings.SESSION_IDLE_TIMEOUT_HOURS * 3600
            await self._redis.set(
                f"sso:saml:assertion:{assertion_id}",
                json.dumps({"consumed_at": datetime.now(UTC).timestamp()}),
                ex=ttl,
            )

        subject_id = str(attrs.get("subject_id", ""))
        email = str(attrs.get("email", ""))
        groups = attrs.get("groups", []) or []
        if isinstance(groups, str):
            groups = [groups]

        try:
            profile, session_id = await self._resolve_role_and_create_session(
                provider=provider,
                subject_id=subject_id,
                email=email,
                groups=groups,
                auth_provider=AuthProvider.SAML,
            )
        except SsoValidationError:
            await AuditService.log(
                self._db,
                action=AuditActionType.AUTH_LOGIN_FAILURE,
                resource_type="sso_callback",
                resource_id="saml",
                outcome="failure",
                context=self._safe_audit_context(error_code="sso_no_role", reason="no_role_assigned"),
            )
            raise

        # Log successful login (must succeed; if it fails, clean up the Redis session)
        try:
            await AuditService.log(
                self._db,
                action=AuditActionType.AUTH_LOGIN_SUCCESS,
                actor_identity=email or subject_id,
                resource_type="user",
                resource_id=str(profile.get("user_id", "")),
                outcome="success",
                context=self._safe_audit_context(
                    auth_provider="saml",
                    role_name=profile.get("role_name"),
                ),
            )
        except Exception:
            # Audit failure: revoke the session we just created so the login
            # cannot be used without an audit trail.
            await self._redis.delete(f"session:{session_id}")
            raise

        return profile, session_id

    def _parse_saml_assertion(self, provider: SsoProvider, saml_response: str) -> dict:
        """Parse and validate SAMLResponse XML; return attribute dict. Override in tests."""
        from onelogin.saml2.auth import OneLogin_Saml2_Auth

        base_url = self._settings.BASE_URL or "https://app.example.com"
        acs_url = f"{base_url}/api/v1/auth/sso/saml/callback"

        req = {
            "https": "on" if base_url.startswith("https://") else "off",
            "http_host": base_url.replace("https://", "").replace("http://", ""),
            "script_name": "/",
            "server_port": "443" if base_url.startswith("https://") else "80",
            "get_data": {},
            "post_data": {
                "SAMLResponse": saml_response,
            },
        }

        idp_entity_id = self._get_idp_entity_id(provider)

        settings_dict = {
            "sp": {
                "entityId": provider.saml_entity_id,
                "assertionConsumerService": {
                    "url": acs_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                },
            },
            "idp": {
                "entityId": idp_entity_id,
                "singleSignOnService": {
                    "url": self._get_idp_sso_url(provider),
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                },
                "x509cert": self._decrypt_saml_certificate(provider),
            },
            "security": {
                "wantAssertionsSigned": True,
                "wantMessagesSigned": False,
            },
        }

        auth = OneLogin_Saml2_Auth(req, settings_dict)
        try:
            auth.process_response()
        except Exception as exc:
            # Sanitize raw python3-saml exceptions (may contain XML, certs, hostnames)
            raise SsoValidationError("SSO assertion validation failed") from exc

        errors = auth.get_errors()
        if errors:
            raise SsoValidationError("SSO assertion validation failed")

        return {
            "subject_id": auth.get_nameid(),
            "email": auth.get_attribute("email")[0] if auth.get_attribute("email") else "",
            "groups": auth.get_attribute(provider.group_claim_name) or [],
            "issuer": auth.get_issuer(),
            "not_before": auth.get_session_not_on_or_after(),
            "not_on_or_after": auth.get_session_not_on_or_after(),
            "assertion_id": auth.get_last_assertion_id(),
        }

    def _validate_saml_assertion(self, attrs: dict, provider: SsoProvider) -> None:
        """Validate SAML assertion attributes per S-002.

        Signature and audience are already enforced by python3-saml
        process_response() with security.wantAssertionsSigned=True.
        This method validates issuer, timestamps, and replay.
        """
        now = datetime.now(UTC)

        issuer = attrs.get("issuer")
        expected_issuer = self._get_idp_entity_id(provider)

        if issuer != expected_issuer:
            raise SsoValidationError("SSO issuer validation failed")

        not_before_str = attrs.get("not_before")
        if not_before_str:
            not_before = datetime.fromisoformat(not_before_str.replace("Z", "+00:00"))
            if not_before > now + self._clock_skew_tolerance:
                raise SsoValidationError("SSO assertion not yet valid")

        not_on_or_after_str = attrs.get("not_on_or_after")
        if not_on_or_after_str:
            not_on_or_after = datetime.fromisoformat(not_on_or_after_str.replace("Z", "+00:00"))
            if not_on_or_after < now - self._clock_skew_tolerance:
                raise SsoValidationError("SSO assertion expired")

    # ------------------------------------------------------------------
    # Role resolution
    # ------------------------------------------------------------------

    async def resolve_role_from_groups(self, groups: list[str]) -> Role | None:
        """Resolve SSO groups to platform role via priority ordering.

        Returns the role with the lowest priority number (highest priority).
        If multiple roles have the same priority, uses name for determinism.
        Returns None if no group maps to a role.
        """
        if not groups:
            return None

        stmt = (
            select(Role)
            .join(SsoGroupMapping, Role.id == SsoGroupMapping.role_id)
            .where(SsoGroupMapping.sso_group_value.in_(groups))
            .order_by(Role.priority.asc(), Role.name.asc())
        )
        result = await self._db.execute(stmt)
        roles = result.scalars().all()
        return roles[0] if roles else None

    # ------------------------------------------------------------------
    # Session creation
    # ------------------------------------------------------------------

    async def _resolve_role_and_create_session(
        self,
        *,
        provider: SsoProvider,
        subject_id: str,
        email: str,
        groups: list[str],
        auth_provider: AuthProvider,
    ) -> tuple[dict, str]:
        """Resolve role, create/update user identity, create Redis session."""
        role = await self.resolve_role_from_groups(groups)
        if role is None:
            raise SsoValidationError("SSO user has no assigned role")

        # Find or create user identity
        identity_stmt = select(UserIdentity).where(
            UserIdentity.provider == str(auth_provider),
            UserIdentity.subject_id == subject_id,
        )
        identity_result = await self._db.execute(identity_stmt)
        identity = identity_result.scalar_one_or_none()

        if identity is None:
            # Create new user
            user = User(
                username=email or subject_id,
                display_name=email or subject_id,
                password_hash=None,
                role_id=role.id,
                auth_provider=str(auth_provider),
            )
            self._db.add(user)
            await self._db.flush()
            await self._db.refresh(user)

            identity = UserIdentity(
                user_id=user.id,
                provider=str(auth_provider),
                subject_id=subject_id,
                email=email,
                sso_groups=groups,
                last_login_at=datetime.now(UTC),
            )
            self._db.add(identity)
            await self._db.flush()
        else:
            # Update existing identity
            identity.sso_groups = groups
            identity.email = email
            identity.last_login_at = datetime.now(UTC)
            user_stmt = select(User).where(User.id == identity.user_id)
            user_result = await self._db.execute(user_stmt)
            user = user_result.scalar_one()
            user.role_id = role.id
            await self._db.flush()

        # Build session
        session_id = os.urandom(32).hex()
        permissions = role.permissions if isinstance(role.permissions, list) else []
        session_data = {
            "user_id": str(user.id),
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "role_id": str(role.id),
            "role_name": role.name,
            "permissions": list(permissions),
            "auth_provider": str(auth_provider),
            "subject_id": subject_id,
            "email": email,
            "created_at": time.time(),
            "last_activity": time.time(),
        }
        ttl = self._settings.SESSION_IDLE_TIMEOUT_HOURS * 3600
        await self._redis.set(
            f"session:{session_id}",
            json.dumps(session_data),
            ex=ttl,
        )

        # Enforce concurrent session limit per user (FR-127, S-010)
        max_sessions = getattr(self._settings, "MAX_CONCURRENT_SESSIONS_PER_USER", 5)
        await SessionRepository.enforce_concurrent_session_limit(
            self._redis,
            str(user.id),
            session_id,
            session_data["created_at"],
            max_sessions,
            ttl,
        )

        profile = {
            "user_id": str(user.id),
            "username": user.username,
            "display_name": user.display_name,
            "role_id": str(role.id),
            "role_name": role.name,
            "permissions": list(permissions),
            "auth_provider": str(auth_provider),
            "subject_id": subject_id,
        }
        return profile, session_id
