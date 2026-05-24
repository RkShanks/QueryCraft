"""Tests for audit secret redaction (T-623)."""

import pytest

from app.db.models.enums import AuditActionType
from app.services.audit_service import AuditService


@pytest.mark.asyncio
class TestAuditRedaction:
    """No secrets, credentials, or full tokens in audit context."""

    async def test_password_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            context={"password": "supersecret"},
        )
        assert entry.context["password"] == "[REDACTED]"

    async def test_api_key_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            context={"api_key": "sk-12345"},
        )
        assert entry.context["api_key"] == "[REDACTED]"

    async def test_nested_secret_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            context={"user": {"name": "alice", "token": "tok-abc"}},
        )
        assert entry.context["user"]["token"] == "[REDACTED]"
        assert entry.context["user"]["name"] == "alice"

    async def test_list_with_secret_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            context={"items": [{"secret": "x"}, {"secret": "y"}]},
        )
        assert entry.context["items"][0]["secret"] == "[REDACTED]"
        assert entry.context["items"][1]["secret"] == "[REDACTED]"

    async def test_client_secret_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.SSO_CONFIG_CHANGE,
            context={"client_secret": "shh"},
        )
        assert entry.context["client_secret"] == "[REDACTED]"

    async def test_access_token_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.AUTH_SSO_VALIDATION,
            context={"access_token": "eyJ..."},
        )
        assert entry.context["access_token"] == "[REDACTED]"

    async def test_certificate_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.SSO_CONFIG_CHANGE,
            context={"certificate": "-----BEGIN CERT-----"},
        )
        assert entry.context["certificate"] == "[REDACTED]"

    async def test_id_token_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.AUTH_SSO_VALIDATION,
            context={"id_token": "eyJid_token..."},
        )
        assert entry.context["id_token"] == "[REDACTED]"

    async def test_jwt_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.AUTH_SSO_VALIDATION,
            context={"jwt": "eyJhbGci..."},
        )
        assert entry.context["jwt"] == "[REDACTED]"

    async def test_authorization_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.AUTH_SSO_VALIDATION,
            context={"Authorization": "Bearer abc123"},
        )
        assert entry.context["Authorization"] == "[REDACTED]"

    async def test_saml_response_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.AUTH_SSO_VALIDATION,
            context={"SAMLResponse": "PHNhbWw+..."},
        )
        assert entry.context["SAMLResponse"] == "[REDACTED]"

    async def test_saml_response_snake_case_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.AUTH_SSO_VALIDATION,
            context={"saml_response": "PHNhbWw+..."},
        )
        assert entry.context["saml_response"] == "[REDACTED]"

    async def test_client_certificate_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.SSO_CONFIG_CHANGE,
            context={"client_certificate": "-----BEGIN CERT-----"},
        )
        assert entry.context["client_certificate"] == "[REDACTED]"

    async def test_private_key_pem_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.SSO_CONFIG_CHANGE,
            context={"private_key_pem": "-----BEGIN RSA PRIVATE KEY-----"},
        )
        assert entry.context["private_key_pem"] == "[REDACTED]"

    async def test_nested_authorization_redacted(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.AUTH_SSO_VALIDATION,
            context={"headers": {"Authorization": "Bearer xyz"}},
        )
        assert entry.context["headers"]["Authorization"] == "[REDACTED]"

    async def test_no_redaction_for_safe_keys(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            context={"question": "hello", "dialect": "postgresql"},
        )
        assert entry.context["question"] == "hello"
        assert entry.context["dialect"] == "postgresql"
