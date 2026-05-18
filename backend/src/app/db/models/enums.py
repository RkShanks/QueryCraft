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


class SchemaIntrospectionStatus(enum.StrEnum):
    """Schema introspection lifecycle states."""

    NONE = "none"
    SUCCESS = "success"
    FAILED = "failed"
    STALE = "stale"
