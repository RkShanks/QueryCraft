"""Phase 3 database enums for source connection management."""

import enum


class DatabaseType(enum.StrEnum):
    """Supported source database types."""

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MSSQL = "mssql"


class LifecycleState(enum.StrEnum):
    """Connection lifecycle states."""

    ACTIVE = "active"
    DISABLED = "disabled"


class HealthStatus(enum.StrEnum):
    """Connection health check results."""

    UNTESTED = "untested"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class Permission(enum.StrEnum):
    """Fixed platform permissions."""

    QUERY_SUBMIT = "query.submit"
    QUERY_HISTORY_VIEW = "query.history.view"
    ADMIN_CONNECTIONS_MANAGE = "admin.connections.manage"
    ADMIN_ROLES_MANAGE = "admin.roles.manage"
    ADMIN_SSO_MANAGE = "admin.sso.manage"
    ADMIN_AUDIT_VERIFY = "admin.audit.verify"


class AuthProvider(enum.StrEnum):
    """Authentication provider types."""

    LOCAL = "local"
    OIDC = "oidc"
    SAML = "saml"


class SsoProtocol(enum.StrEnum):
    """SSO protocol types."""

    OIDC = "oidc"
    SAML = "saml"


class AuditActionType(enum.StrEnum):
    """Tamper-evident audit log action types."""

    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILURE = "auth.login.failure"
    AUTH_LOGOUT = "auth.logout"
    AUTH_SSO_VALIDATION = "auth.sso.validation"
    QUERY_SUBMIT = "query.submit"
    QUERY_VALIDATE_PASS = "query.validate.pass"
    QUERY_VALIDATE_FAIL = "query.validate.fail"
    QUERY_EXECUTE = "query.execute"
    QUERY_ACCEPT = "query.accept"
    QUERY_REJECT = "query.reject"
    ROLE_CREATE = "role.create"
    ROLE_UPDATE = "role.update"
    ROLE_DELETE = "role.delete"
    ROLE_MAPPING_CHANGE = "role.mapping.change"
    SSO_CONFIG_CHANGE = "sso.config.change"
    CONNECTION_CREATE = "connection.create"
    CONNECTION_UPDATE = "connection.update"
    CONNECTION_DELETE = "connection.delete"
    ADMIN_CONFIG_CHANGE = "admin.config.change"
    ACCESS_DENIED = "access.denied"
    AUDIT_VERIFY = "audit.verify"
    POLICY_SCHEMA_MISMATCH = "policy.schema_mismatch"


class SchemaIntrospectionStatus(enum.StrEnum):
    """Schema introspection lifecycle states."""

    NONE = "none"
    SUCCESS = "success"
    FAILED = "failed"
    STALE = "stale"
