"""Phase 3 database enums for source connection management."""

import enum


class DatabaseType(str, enum.Enum):
    """Supported source database types."""

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MSSQL = "mssql"


class LifecycleState(str, enum.Enum):
    """Connection lifecycle states."""

    ACTIVE = "active"
    DISABLED = "disabled"


class HealthStatus(str, enum.Enum):
    """Connection health check results."""

    UNTESTED = "untested"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class SchemaIntrospectionStatus(str, enum.Enum):
    """Schema introspection lifecycle states."""

    NONE = "none"
    SUCCESS = "success"
    FAILED = "failed"
    STALE = "stale"
