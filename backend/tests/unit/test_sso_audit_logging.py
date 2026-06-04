"""TDD tests for SSO audit logging (T-654).

Covers:
- SSO login success (OIDC + SAML) → auth.login.success
- SSO login failure (OIDC + SAML) → auth.login.failure
- SSO validation events → auth.sso.validation
- SSO config changes (admin CRUD) → sso.config.change
- Audit context redaction: no raw tokens, certs, assertion XML, client secrets,
  metadata XML, hostnames, UUIDs, or DB errors in audit entries.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.enums import AuditActionType, SsoProtocol
from app.db.models.role import Role
from app.db.models.sso_provider import SsoProvider
from app.db.models.user import User
from app.db.models.user_identity import UserIdentity
from app.services.audit_service import AuditService
from app.services.sso_service import SsoService, SsoValidationError

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_oidc_provider():
    p = MagicMock(spec=SsoProvider)
    p.id = uuid.uuid4()
    p.protocol = SsoProtocol.OIDC
    p.display_name = "Test OIDC"
    p.issuer_url = "https://idp.example.com"
    p.client_id = "client-123"
    p.encrypted_client_secret = "enc-secret"
    p.scopes = "openid email profile groups"
    p.redirect_uri = "https://app.example.com/callback"
    p.group_claim_name = "groups"
    p.saml_entity_id = None
    p.saml_metadata_url = None
    p.encrypted_saml_metadata_xml = None
    p.encrypted_saml_certificate = None
    p.is_active = True
    return p


def _make_saml_provider():
    p = MagicMock(spec=SsoProvider)
    p.id = uuid.uuid4()
    p.protocol = SsoProtocol.SAML
    p.display_name = "Test SAML"
    p.issuer_url = None
    p.client_id = None
    p.encrypted_client_secret = None
    p.scopes = None
    p.redirect_uri = None
    p.group_claim_name = "groups"
    p.saml_entity_id = "https://app.example.com/sp"
    p.saml_metadata_url = "https://idp.example.com/metadata"
    p.encrypted_saml_metadata_xml = "enc-metadata"
    p.encrypted_saml_certificate = "enc-cert"
    p.is_active = True
    return p


def _make_role():
    r = MagicMock(spec=Role)
    r.id = uuid.uuid4()
    r.name = "Analyst"
    r.priority = 10
    r.permissions = ["query.submit", "query.history.view"]
    r.is_builtin = False
    return r


class FakeResult:
    """Mock SQLAlchemy result."""

    def __init__(self, items):
        self._items = items if isinstance(items, list) else [items]

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def first(self):
        return self._items[0] if self._items else None


# ── SSO Service — OIDC Audit Logging ────────────────────────────────────────


@pytest.mark.asyncio
class TestSsoServiceOidcAuditLogging:
    """AuditService.log is called during OIDC callback processing."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock()
        redis.set = AsyncMock()
        return redis

    @pytest.fixture
    def service(self, mock_db, mock_redis):
        svc = SsoService(mock_db, mock_redis)
        # Patch settings to avoid config lookups
        svc._settings = MagicMock()
        svc._settings.SESSION_IDLE_TIMEOUT_HOURS = 8
        svc._settings.PLATFORM_ENCRYPTION_KEY = "test-key"
        return svc

    async def test_oidc_callback_success_logs_login_success(self, service, mock_db, mock_redis):
        """On successful OIDC login, audit log records auth.login.success."""
        provider = _make_oidc_provider()
        role = _make_role()
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.username = "alice@example.com"
        user.display_name = "Alice"
        user.role_id = role.id
        user.role = "analyst"
        user.auth_provider = "oidc"

        identity = MagicMock(spec=UserIdentity)
        identity.user_id = user.id
        identity.sso_groups = ["analysts"]
        identity.email = "alice@example.com"

        # Redis state lookup
        mock_redis.get = AsyncMock(return_value='{"nonce": "test-nonce", "provider_id": "' + str(provider.id) + '"}')

        # Patch exchange + validation + role resolution to avoid real IdP
        with (
            patch.object(
                service,
                "_exchange_code_for_token",
                return_value=(
                    {"sub": "user-123", "email": "alice@example.com", "groups": ["analysts"]},
                    "access-token",
                ),
            ),
            patch.object(service, "_validate_oidc_claims", return_value=None),
            patch.object(service, "resolve_role_from_groups", return_value=role),
        ):
            # DB returns no existing identity → creates new user
            mock_db.execute = AsyncMock(
                side_effect=[
                    FakeResult([]),  # identity lookup
                    FakeResult([user]),  # user lookup after flush (not used directly)
                ]
            )

            with patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as mock_audit:
                await service.process_oidc_callback(provider, "state-123", "code-123")

                # Assert audit.log was called with auth.login.success
                mock_audit.assert_called()
                calls = [
                    c for c in mock_audit.call_args_list if c.kwargs.get("action") == AuditActionType.AUTH_LOGIN_SUCCESS
                ]
                assert len(calls) >= 1, f"Expected auth.login.success audit call, got {mock_audit.call_args_list}"

    async def test_oidc_callback_failure_logs_login_failure(self, service, mock_db, mock_redis):
        """On OIDC validation failure, audit log records auth.login.failure."""
        provider = _make_oidc_provider()

        mock_redis.get = AsyncMock(return_value='{"nonce": "test-nonce", "provider_id": "' + str(provider.id) + '"}')

        with (
            patch.object(
                service, "_exchange_code_for_token", side_effect=SsoValidationError("SSO token exchange failed")
            ),
            patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as mock_audit,
        ):
            with pytest.raises(SsoValidationError):
                await service.process_oidc_callback(provider, "state-123", "code-123")

            mock_audit.assert_called()
            calls = [
                c for c in mock_audit.call_args_list if c.kwargs.get("action") == AuditActionType.AUTH_LOGIN_FAILURE
            ]
            assert len(calls) >= 1, f"Expected auth.login.failure audit call, got {mock_audit.call_args_list}"

    async def test_oidc_callback_validation_event_logged(self, service, mock_db, mock_redis):
        """OIDC token validation emits auth.sso.validation audit event."""
        provider = _make_oidc_provider()
        role = _make_role()
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.username = "alice@example.com"
        user.display_name = "Alice"
        user.role_id = role.id
        user.role = "analyst"
        user.auth_provider = "oidc"

        mock_redis.get = AsyncMock(return_value='{"nonce": "test-nonce", "provider_id": "' + str(provider.id) + '"}')

        with (
            patch.object(
                service,
                "_exchange_code_for_token",
                return_value=(
                    {"sub": "user-123", "email": "alice@example.com", "groups": ["analysts"]},
                    "access-token",
                ),
            ),
            patch.object(service, "_validate_oidc_claims", return_value=None),
            patch.object(service, "resolve_role_from_groups", return_value=role),
        ):
            mock_db.execute = AsyncMock(
                side_effect=[
                    FakeResult([]),
                    FakeResult([user]),
                ]
            )

            with patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as mock_audit:
                await service.process_oidc_callback(provider, "state-123", "code-123")

                mock_audit.assert_called()
                validation_calls = [
                    c
                    for c in mock_audit.call_args_list
                    if c.kwargs.get("action") == AuditActionType.AUTH_SSO_VALIDATION
                ]
                assert len(validation_calls) >= 1, (
                    f"Expected auth.sso.validation audit call, got {mock_audit.call_args_list}"
                )

    async def test_oidc_audit_context_no_raw_tokens(self, service, mock_db, mock_redis):
        """Audit context must not contain raw ID tokens, access tokens, or secrets."""
        provider = _make_oidc_provider()
        role = _make_role()
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.username = "alice@example.com"
        user.display_name = "Alice"
        user.role_id = role.id
        user.role = "analyst"
        user.auth_provider = "oidc"

        mock_redis.get = AsyncMock(return_value='{"nonce": "test-nonce", "provider_id": "' + str(provider.id) + '"}')

        with (
            patch.object(
                service,
                "_exchange_code_for_token",
                return_value=(
                    {"sub": "user-123", "email": "alice@example.com", "groups": ["analysts"]},
                    "access-token-xyz",
                ),
            ),
            patch.object(service, "_validate_oidc_claims", return_value=None),
            patch.object(service, "resolve_role_from_groups", return_value=role),
        ):
            mock_db.execute = AsyncMock(
                side_effect=[
                    FakeResult([]),
                    FakeResult([user]),
                ]
            )

            with patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as mock_audit:
                await service.process_oidc_callback(provider, "state-123", "code-123")

                for call in mock_audit.call_args_list:
                    ctx = call.kwargs.get("context", {})
                    # No raw tokens in context
                    for key in ["id_token", "access_token", "token", "code", "client_secret", "nonce", "state"]:
                        if key in ctx:
                            assert ctx[key] == "[REDACTED]" or "[REDACTED]" in str(ctx[key]), (
                                f"Raw {key} found in audit context: {ctx}"
                            )

    async def test_oidc_audit_context_no_hostname_or_uuid_leak(self, service, mock_db, mock_redis):
        """Audit context must not leak issuer hostname or provider UUID."""
        provider = _make_oidc_provider()
        role = _make_role()
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.username = "alice@example.com"
        user.display_name = "Alice"
        user.role_id = role.id
        user.role = "analyst"
        user.auth_provider = "oidc"

        mock_redis.get = AsyncMock(return_value='{"nonce": "test-nonce", "provider_id": "' + str(provider.id) + '"}')

        with (
            patch.object(
                service,
                "_exchange_code_for_token",
                return_value=({"sub": "user-123", "email": "alice@example.com", "groups": ["analysts"]}, "token"),
            ),
            patch.object(service, "_validate_oidc_claims", return_value=None),
            patch.object(service, "resolve_role_from_groups", return_value=role),
        ):
            mock_db.execute = AsyncMock(
                side_effect=[
                    FakeResult([]),
                    FakeResult([user]),
                ]
            )

            with patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as mock_audit:
                await service.process_oidc_callback(provider, "state-123", "code-123")

                for call in mock_audit.call_args_list:
                    ctx = call.kwargs.get("context", {})
                    ctx_str = str(ctx)
                    # No hostname leak
                    assert "idp.example.com" not in ctx_str, f"Hostname leaked in audit context: {ctx}"
                    # No provider UUID leak
                    assert str(provider.id) not in ctx_str, f"Provider UUID leaked in audit context: {ctx}"


# ── SSO Service — SAML Audit Logging ──────────────────────────────────────────


@pytest.mark.asyncio
class TestSsoServiceSamlAuditLogging:
    """AuditService.log is called during SAML callback processing."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock()
        redis.set = AsyncMock()
        return redis

    @pytest.fixture
    def service(self, mock_db, mock_redis):
        svc = SsoService(mock_db, mock_redis)
        svc._settings = MagicMock()
        svc._settings.SESSION_IDLE_TIMEOUT_HOURS = 8
        svc._settings.PLATFORM_ENCRYPTION_KEY = "test-key"
        svc._settings.BASE_URL = "https://app.example.com"
        return svc

    async def test_saml_callback_success_logs_login_success(self, service, mock_db, mock_redis):
        """On successful SAML login, audit log records auth.login.success."""
        provider = _make_saml_provider()
        role = _make_role()
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.username = "bob@example.com"
        user.display_name = "Bob"
        user.role_id = role.id
        user.role = "analyst"
        user.auth_provider = "saml"

        def _redis_get_side_effect(key):
            if "request:" in key:
                return '{"provider_id": "' + str(provider.id) + '"}'
            return None

        mock_redis.get = AsyncMock(side_effect=_redis_get_side_effect)

        attrs = {
            "subject_id": "user-456",
            "email": "bob@example.com",
            "groups": ["analysts"],
            "issuer": "https://idp.example.com",
            "not_before": None,
            "not_on_or_after": None,
            "assertion_id": "assertion-001",
        }

        with (
            patch.object(service, "_parse_saml_assertion", return_value=attrs),
            patch.object(service, "_validate_saml_assertion", return_value=None),
            patch.object(service, "resolve_role_from_groups", return_value=role),
        ):
            mock_db.execute = AsyncMock(
                side_effect=[
                    FakeResult([]),
                    FakeResult([user]),
                ]
            )

            with patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as mock_audit:
                await service.process_saml_callback(provider, "saml-response-xml", "request-123")

                mock_audit.assert_called()
                success_calls = [
                    c for c in mock_audit.call_args_list if c.kwargs.get("action") == AuditActionType.AUTH_LOGIN_SUCCESS
                ]
                assert len(success_calls) >= 1, (
                    f"Expected auth.login.success audit call, got {mock_audit.call_args_list}"
                )

    async def test_saml_callback_failure_logs_login_failure(self, service, mock_db, mock_redis):
        """On SAML validation failure, audit log records auth.login.failure."""
        provider = _make_saml_provider()

        def _redis_get_side_effect(key):
            if "request:" in key:
                return '{"provider_id": "' + str(provider.id) + '"}'
            return None

        mock_redis.get = AsyncMock(side_effect=_redis_get_side_effect)

        with (
            patch.object(
                service, "_parse_saml_assertion", side_effect=SsoValidationError("SSO assertion validation failed")
            ),
            patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as mock_audit,
        ):
            with pytest.raises(SsoValidationError):
                await service.process_saml_callback(provider, "bad-xml", "request-123")

            mock_audit.assert_called()
            failure_calls = [
                c for c in mock_audit.call_args_list if c.kwargs.get("action") == AuditActionType.AUTH_LOGIN_FAILURE
            ]
            assert len(failure_calls) >= 1, f"Expected auth.login.failure audit call, got {mock_audit.call_args_list}"

    async def test_saml_callback_validation_event_logged(self, service, mock_db, mock_redis):
        """SAML assertion validation emits auth.sso.validation audit event."""
        provider = _make_saml_provider()
        role = _make_role()
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.username = "bob@example.com"
        user.display_name = "Bob"
        user.role_id = role.id
        user.role = "analyst"
        user.auth_provider = "saml"

        def _redis_get_side_effect(key):
            if "request:" in key:
                return '{"provider_id": "' + str(provider.id) + '"}'
            return None

        mock_redis.get = AsyncMock(side_effect=_redis_get_side_effect)

        attrs = {
            "subject_id": "user-456",
            "email": "bob@example.com",
            "groups": ["analysts"],
            "issuer": "https://idp.example.com",
            "not_before": None,
            "not_on_or_after": None,
            "assertion_id": "assertion-001",
        }

        with (
            patch.object(service, "_parse_saml_assertion", return_value=attrs),
            patch.object(service, "_validate_saml_assertion", return_value=None),
            patch.object(service, "resolve_role_from_groups", return_value=role),
        ):
            mock_db.execute = AsyncMock(
                side_effect=[
                    FakeResult([]),
                    FakeResult([user]),
                ]
            )

            with patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as mock_audit:
                await service.process_saml_callback(provider, "saml-response-xml", "request-123")

                mock_audit.assert_called()
                validation_calls = [
                    c
                    for c in mock_audit.call_args_list
                    if c.kwargs.get("action") == AuditActionType.AUTH_SSO_VALIDATION
                ]
                assert len(validation_calls) >= 1, (
                    f"Expected auth.sso.validation audit call, got {mock_audit.call_args_list}"
                )

    async def test_saml_audit_context_no_assertion_xml(self, service, mock_db, mock_redis):
        """Audit context must not contain raw SAML assertion XML."""
        provider = _make_saml_provider()
        role = _make_role()
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.username = "bob@example.com"
        user.display_name = "Bob"
        user.role_id = role.id
        user.role = "analyst"
        user.auth_provider = "saml"

        def _redis_get_side_effect(key):
            if "request:" in key:
                return '{"provider_id": "' + str(provider.id) + '"}'
            return None

        mock_redis.get = AsyncMock(side_effect=_redis_get_side_effect)

        attrs = {
            "subject_id": "user-456",
            "email": "bob@example.com",
            "groups": ["analysts"],
            "issuer": "https://idp.example.com",
            "not_before": None,
            "not_on_or_after": None,
            "assertion_id": "assertion-001",
        }

        with (
            patch.object(service, "_parse_saml_assertion", return_value=attrs),
            patch.object(service, "_validate_saml_assertion", return_value=None),
            patch.object(service, "resolve_role_from_groups", return_value=role),
        ):
            mock_db.execute = AsyncMock(
                side_effect=[
                    FakeResult([]),
                    FakeResult([user]),
                ]
            )

            with patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as mock_audit:
                await service.process_saml_callback(provider, "<saml>raw-xml</saml>", "request-123")

                for call in mock_audit.call_args_list:
                    ctx = call.kwargs.get("context", {})
                    ctx_str = str(ctx)
                    assert "<saml>" not in ctx_str, f"Raw SAML XML leaked in audit context: {ctx}"
                    assert "raw-xml" not in ctx_str, f"Raw SAML content leaked in audit context: {ctx}"

    async def test_saml_audit_context_no_certificate(self, service, mock_db, mock_redis):
        """Audit context must not contain SAML certificate content."""
        provider = _make_saml_provider()
        role = _make_role()
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.username = "bob@example.com"
        user.display_name = "Bob"
        user.role_id = role.id
        user.role = "analyst"
        user.auth_provider = "saml"

        def _redis_get_side_effect(key):
            if "request:" in key:
                return '{"provider_id": "' + str(provider.id) + '"}'
            return None

        mock_redis.get = AsyncMock(side_effect=_redis_get_side_effect)

        attrs = {
            "subject_id": "user-456",
            "email": "bob@example.com",
            "groups": ["analysts"],
            "issuer": "https://idp.example.com",
            "not_before": None,
            "not_on_or_after": None,
            "assertion_id": "assertion-001",
        }

        with (
            patch.object(service, "_parse_saml_assertion", return_value=attrs),
            patch.object(service, "_validate_saml_assertion", return_value=None),
            patch.object(service, "resolve_role_from_groups", return_value=role),
        ):
            mock_db.execute = AsyncMock(
                side_effect=[
                    FakeResult([]),
                    FakeResult([user]),
                ]
            )

            with patch("app.services.audit_service.AuditService.log", new_callable=AsyncMock) as mock_audit:
                await service.process_saml_callback(provider, "saml-response", "request-123")

                for call in mock_audit.call_args_list:
                    ctx = call.kwargs.get("context", {})
                    ctx_str = str(ctx)
                    assert "BEGIN CERTIFICATE" not in ctx_str, f"Certificate leaked in audit context: {ctx}"
                    assert "enc-cert" not in ctx_str, f"Encrypted cert reference leaked in audit context: {ctx}"


# ── Admin SSO Endpoints — Config Change Audit Logging ────────────────────────


@pytest.mark.asyncio
class TestAdminSsoAuditLogging:
    """Admin SSO CRUD endpoints emit sso.config.change audit events."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.flush = AsyncMock()
        return db

    @pytest.fixture
    def admin_request(self):
        req = MagicMock()
        req.state.session = {
            "permissions": ["admin.sso.manage"],
            "user_id": "admin-uuid",
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        }
        return req

    async def test_create_provider_logs_sso_config_change(self, mock_db, admin_request):
        """POST /admin/sso/providers creates sso.config.change audit entry."""
        from app.api.v1.admin_sso import create_provider
        from app.schemas.sso import SsoProviderCreate

        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),  # no duplicate
                FakeResult([MagicMock()]),  # RETURNING
            ]
        )

        body = SsoProviderCreate(
            protocol="oidc",
            display_name="New Provider",
            issuer_url="https://idp.example.com",
            client_id="client-123",
            client_secret="secret-123",
        )

        with (
            patch("app.api.v1.admin_sso.encrypt", return_value="encrypted"),
            patch("app.api.v1.admin_sso.AuditService.log", new_callable=AsyncMock) as mock_audit,
        ):
            await create_provider(request=admin_request, body=body, db=mock_db)

            mock_audit.assert_called()
            config_calls = [
                c for c in mock_audit.call_args_list if c.kwargs.get("action") == AuditActionType.SSO_CONFIG_CHANGE
            ]
            assert len(config_calls) >= 1, f"Expected sso.config.change audit call, got {mock_audit.call_args_list}"

    async def test_update_provider_logs_sso_config_change(self, mock_db, admin_request):
        """PUT /admin/sso/providers/{id} creates sso.config.change audit entry."""
        from app.api.v1.admin_sso import update_provider
        from app.schemas.sso import SsoProviderUpdate

        provider = _make_oidc_provider()
        mock_db.execute = AsyncMock(return_value=FakeResult([provider]))

        body = SsoProviderUpdate(display_name="Updated Name")

        with (
            patch("app.api.v1.admin_sso.encrypt", return_value="encrypted"),
            patch("app.api.v1.admin_sso.AuditService.log", new_callable=AsyncMock) as mock_audit,
        ):
            await update_provider(
                request=admin_request,
                provider_id=str(provider.id),
                body=body,
                db=mock_db,
            )

            mock_audit.assert_called()
            config_calls = [
                c for c in mock_audit.call_args_list if c.kwargs.get("action") == AuditActionType.SSO_CONFIG_CHANGE
            ]
            assert len(config_calls) >= 1, f"Expected sso.config.change audit call, got {mock_audit.call_args_list}"

    async def test_delete_provider_logs_sso_config_change(self, mock_db, admin_request):
        """DELETE /admin/sso/providers/{id} creates sso.config.change audit entry."""
        from app.api.v1.admin_sso import delete_provider

        provider = _make_oidc_provider()
        mock_db.execute = AsyncMock(return_value=FakeResult([provider]))

        with patch("app.api.v1.admin_sso.AuditService.log", new_callable=AsyncMock) as mock_audit:
            await delete_provider(
                request=admin_request,
                provider_id=str(provider.id),
                db=mock_db,
            )

            mock_audit.assert_called()
            config_calls = [
                c for c in mock_audit.call_args_list if c.kwargs.get("action") == AuditActionType.SSO_CONFIG_CHANGE
            ]
            assert len(config_calls) >= 1, f"Expected sso.config.change audit call, got {mock_audit.call_args_list}"

    async def test_admin_audit_context_no_secrets(self, mock_db, admin_request):
        """Admin SSO audit context must not contain raw client secrets or certificates."""
        from app.api.v1.admin_sso import create_provider
        from app.schemas.sso import SsoProviderCreate

        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),
                FakeResult([MagicMock()]),
            ]
        )

        body = SsoProviderCreate(
            protocol="oidc",
            display_name="New Provider",
            issuer_url="https://idp.example.com",
            client_id="client-123",
            client_secret="super-secret-value",
        )

        with (
            patch("app.api.v1.admin_sso.encrypt", return_value="encrypted"),
            patch("app.api.v1.admin_sso.AuditService.log", new_callable=AsyncMock) as mock_audit,
        ):
            await create_provider(request=admin_request, body=body, db=mock_db)

            for call in mock_audit.call_args_list:
                ctx = call.kwargs.get("context", {})
                ctx_str = str(ctx)
                assert "super-secret-value" not in ctx_str, f"Raw secret leaked in audit context: {ctx}"
                assert "client_secret" not in ctx_str or "[REDACTED]" in ctx_str, (
                    f"Unredacted client_secret in audit context: {ctx}"
                )


# ── Audit Redaction Integration ──────────────────────────────────────────────


@pytest.mark.asyncio
class TestSsoAuditRedactionIntegration:
    """Verify AuditService redaction is applied to SSO audit entries."""

    async def test_sso_config_audit_redacts_client_secret(self, db_session):
        """sso.config.change with client_secret in context is redacted by AuditService."""
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.SSO_CONFIG_CHANGE,
            actor_identity="admin",
            resource_type="sso_provider",
            resource_id="provider-123",
            outcome="success",
            context={
                "protocol": "oidc",
                "display_name": "Corp SSO",
                "client_secret": "should-be-redacted",
                "saml_certificate": "should-be-redacted-too",
            },
        )
        assert entry.context["client_secret"] == "[REDACTED]"
        assert entry.context["saml_certificate"] == "[REDACTED]"
        assert entry.context["protocol"] == "oidc"
        assert entry.context["display_name"] == "Corp SSO"

    async def test_sso_validation_audit_redacts_tokens(self, db_session):
        """auth.sso.validation with tokens in context is redacted by AuditService."""
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.AUTH_SSO_VALIDATION,
            actor_identity="alice",
            resource_type="sso_callback",
            outcome="success",
            context={
                "provider": "oidc",
                "id_token": "eyJhbGci...",
                "access_token": "sl.access...",
                "saml_response": "PHNhbWw+",
            },
        )
        assert entry.context["id_token"] == "[REDACTED]"
        assert entry.context["access_token"] == "[REDACTED]"
        assert entry.context["saml_response"] == "[REDACTED]"
        assert entry.context["provider"] == "oidc"

    async def test_sso_login_failure_audit_redacts_error_details(self, db_session):
        """auth.login.failure context contains sanitized error only."""
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.AUTH_LOGIN_FAILURE,
            actor_identity="bob",
            resource_type="sso_callback",
            outcome="failure",
            context={
                "provider": "saml",
                "error_code": "sso_validation_failed",
                # Raw error details should not be present; if they are, redaction applies
                "assertion_xml": "<saml>secret</saml>",
            },
        )
        assert entry.context["assertion_xml"] == "[REDACTED]"
        assert entry.context["error_code"] == "sso_validation_failed"
        assert entry.context["provider"] == "saml"


# ── Review Fix 1: Admin SSO Audit Atomicity ──────────────────────────────────


@pytest.mark.asyncio
class TestAdminSsoAuditAtomicity:
    """Audit log must be written inside the same transaction as provider mutation.
    If audit fails, the provider change must not persist (no commit)."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def admin_request(self):
        req = MagicMock()
        req.state.session = {
            "permissions": ["admin.sso.manage"],
            "username": "admin",
            "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        }
        return req

    async def test_create_audit_failure_prevents_commit(self, mock_db, admin_request):
        """If AuditService.log raises during create, db.commit must not be called."""
        from fastapi import HTTPException

        from app.api.v1.admin_sso import create_provider
        from app.schemas.sso import SsoProviderCreate

        mock_db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),  # no duplicate
                FakeResult([MagicMock()]),  # RETURNING
            ]
        )

        body = SsoProviderCreate(
            protocol="oidc",
            display_name="New Provider",
            issuer_url="https://idp.example.com",
            client_id="client-123",
            client_secret="secret-123",
        )

        with (
            patch("app.api.v1.admin_sso.encrypt", return_value="encrypted"),
            patch(
                "app.api.v1.admin_sso.AuditService.log",
                new_callable=AsyncMock,
                side_effect=RuntimeError("audit failure"),
            ),
        ):
            with pytest.raises(HTTPException):
                await create_provider(request=admin_request, body=body, db=mock_db)

        # commit must never have been called
        mock_db.commit.assert_not_called()

    async def test_update_audit_failure_prevents_commit(self, mock_db, admin_request):
        """If AuditService.log raises during update, db.commit must not be called."""
        from fastapi import HTTPException

        from app.api.v1.admin_sso import update_provider
        from app.schemas.sso import SsoProviderUpdate

        provider = _make_oidc_provider()
        mock_db.execute = AsyncMock(return_value=FakeResult([provider]))

        body = SsoProviderUpdate(display_name="Updated Name")

        with (
            patch("app.api.v1.admin_sso.encrypt", return_value="encrypted"),
            patch(
                "app.api.v1.admin_sso.AuditService.log",
                new_callable=AsyncMock,
                side_effect=RuntimeError("audit failure"),
            ),
        ):
            with pytest.raises(HTTPException):
                await update_provider(
                    request=admin_request,
                    provider_id=str(provider.id),
                    body=body,
                    db=mock_db,
                )

        mock_db.commit.assert_not_called()

    async def test_delete_audit_failure_prevents_commit(self, mock_db, admin_request):
        """If AuditService.log raises during delete, db.commit must not be called."""
        from fastapi import HTTPException

        from app.api.v1.admin_sso import delete_provider

        provider = _make_oidc_provider()
        mock_db.execute = AsyncMock(return_value=FakeResult([provider]))

        with patch(
            "app.api.v1.admin_sso.AuditService.log",
            new_callable=AsyncMock,
            side_effect=RuntimeError("audit failure"),
        ):
            with pytest.raises(HTTPException):
                await delete_provider(
                    request=admin_request,
                    provider_id=str(provider.id),
                    db=mock_db,
                )

        mock_db.commit.assert_not_called()


# ── Review Fix 2: SSO Login Session Cleanup on Audit Failure ───────────────────


@pytest.mark.asyncio
class TestSsoLoginAuditCleanup:
    """If auth.login.success audit logging fails after session creation,
    the Redis session must be deleted so the login cannot be used unaudited."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock()
        redis.set = AsyncMock()
        return redis

    @pytest.fixture
    def service(self, mock_db, mock_redis):
        svc = SsoService(mock_db, mock_redis)
        svc._settings = MagicMock()
        svc._settings.SESSION_IDLE_TIMEOUT_HOURS = 8
        svc._settings.PLATFORM_ENCRYPTION_KEY = "test-key"
        return svc

    async def test_oidc_audit_failure_deletes_session(self, service, mock_db, mock_redis):
        """If auth.login.success audit fails, the Redis session is revoked."""
        provider = _make_oidc_provider()
        role = _make_role()
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.username = "alice@example.com"
        user.display_name = "Alice"
        user.role_id = role.id
        user.role = "analyst"
        user.auth_provider = "oidc"

        mock_redis.get = AsyncMock(return_value='{"nonce": "test-nonce", "provider_id": "' + str(provider.id) + '"}')

        with (
            patch.object(
                service,
                "_exchange_code_for_token",
                return_value=(
                    {"sub": "user-123", "email": "alice@example.com", "groups": ["analysts"]},
                    "token",
                ),
            ),
            patch.object(service, "_validate_oidc_claims", return_value=None),
            patch.object(service, "resolve_role_from_groups", return_value=role),
        ):
            mock_db.execute = AsyncMock(
                side_effect=[
                    FakeResult([]),
                    FakeResult([user]),
                ]
            )

            with patch(
                "app.services.audit_service.AuditService.log",
                new_callable=AsyncMock,
                side_effect=[
                    None,  # auth.sso.validation success
                    RuntimeError("audit failure"),  # auth.login.success failure
                ],
            ):
                with pytest.raises(RuntimeError, match="audit failure"):
                    await service.process_oidc_callback(provider, "state-123", "code-123")

                # Verify the session was deleted from Redis
                redis_delete_calls = [c for c in mock_redis.delete.call_args_list if "session:" in str(c)]
                assert len(redis_delete_calls) >= 1, (
                    f"Expected Redis session delete on audit failure, got {mock_redis.delete.call_args_list}"
                )
                # Verify user session index cleaned up
                zrem_calls = [c for c in mock_redis.zrem.call_args_list if "user_sessions:" in str(c[0][0])]
                assert len(zrem_calls) >= 1, (
                    f"Expected user_sessions zrem on audit failure, got {mock_redis.zrem.call_args_list}"
                )

    async def test_saml_audit_failure_deletes_session(self, service, mock_db, mock_redis):
        """If auth.login.success audit fails, the Redis session is revoked."""
        provider = _make_saml_provider()
        role = _make_role()
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.username = "bob@example.com"
        user.display_name = "Bob"
        user.role_id = role.id
        user.role = "analyst"
        user.auth_provider = "saml"

        def _redis_get_side_effect(key):
            if "request:" in key:
                return '{"provider_id": "' + str(provider.id) + '"}'
            return None

        mock_redis.get = AsyncMock(side_effect=_redis_get_side_effect)

        attrs = {
            "subject_id": "user-456",
            "email": "bob@example.com",
            "groups": ["analysts"],
            "issuer": "https://idp.example.com",
            "not_before": None,
            "not_on_or_after": None,
            "assertion_id": "assertion-001",
        }

        with (
            patch.object(service, "_parse_saml_assertion", return_value=attrs),
            patch.object(service, "_validate_saml_assertion", return_value=None),
            patch.object(service, "resolve_role_from_groups", return_value=role),
        ):
            mock_db.execute = AsyncMock(
                side_effect=[
                    FakeResult([]),
                    FakeResult([user]),
                ]
            )

            with patch(
                "app.services.audit_service.AuditService.log",
                new_callable=AsyncMock,
                side_effect=[
                    None,  # auth.sso.validation success
                    RuntimeError("audit failure"),  # auth.login.success failure
                ],
            ):
                with pytest.raises(RuntimeError, match="audit failure"):
                    await service.process_saml_callback(provider, "saml-response", "request-123")

                # Verify the session was deleted from Redis
                redis_delete_calls = [c for c in mock_redis.delete.call_args_list if "session:" in str(c)]
                assert len(redis_delete_calls) >= 1, (
                    f"Expected Redis session delete on audit failure, got {mock_redis.delete.call_args_list}"
                )
                # Verify user session index cleaned up
                zrem_calls = [c for c in mock_redis.zrem.call_args_list if "user_sessions:" in str(c[0][0])]
                assert len(zrem_calls) >= 1, (
                    f"Expected user_sessions zrem on audit failure, got {mock_redis.zrem.call_args_list}"
                )
