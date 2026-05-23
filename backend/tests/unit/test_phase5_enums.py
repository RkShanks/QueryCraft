"""Tests for Phase 5 enums (T-601–T-604)."""

from app.db.models.enums import AuditActionType, AuthProvider, Permission, SsoProtocol


class TestPermissionEnum:
    """T-601: Permission enum fixed set."""

    def test_members(self):
        assert Permission.QUERY_SUBMIT == "query.submit"
        assert Permission.QUERY_HISTORY_VIEW == "query.history.view"
        assert Permission.ADMIN_CONNECTIONS_MANAGE == "admin.connections.manage"
        assert Permission.ADMIN_ROLES_MANAGE == "admin.roles.manage"
        assert Permission.ADMIN_SSO_MANAGE == "admin.sso.manage"
        assert Permission.ADMIN_AUDIT_VERIFY == "admin.audit.verify"

    def test_is_strenum(self):
        assert issubclass(Permission, str)


class TestAuthProviderEnum:
    """T-602: AuthProvider enum."""

    def test_members(self):
        assert AuthProvider.LOCAL == "local"
        assert AuthProvider.OIDC == "oidc"
        assert AuthProvider.SAML == "saml"


class TestSsoProtocolEnum:
    """T-603: SsoProtocol enum."""

    def test_members(self):
        assert SsoProtocol.OIDC == "oidc"
        assert SsoProtocol.SAML == "saml"


class TestAuditActionTypeEnum:
    """T-604: AuditActionType enum — all 22 action types."""

    def test_all_members_present(self):
        expected = {
            "auth.login.success",
            "auth.login.failure",
            "auth.logout",
            "auth.sso.validation",
            "query.submit",
            "query.validate.pass",
            "query.validate.fail",
            "query.execute",
            "query.accept",
            "query.reject",
            "role.create",
            "role.update",
            "role.delete",
            "role.mapping.change",
            "sso.config.change",
            "connection.create",
            "connection.update",
            "connection.delete",
            "admin.config.change",
            "access.denied",
            "audit.verify",
            "policy.schema_mismatch",
        }
        actual = {m.value for m in AuditActionType}
        assert actual == expected
