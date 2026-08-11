"""010_persisted_security_resource_invariants

Revision ID: 010
Revises: 009
Create Date: 2026-08-11
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PREFLIGHT_REFUSAL = "Revision 010 preflight refused: persisted invariant repair is required before retry."
_PREFLIGHT_SQL = sa.text(
    """
    SELECT
        (SELECT count(*) FROM role_quotas
         WHERE daily_query_limit < 0
            OR daily_execution_limit < 0
            OR daily_export_limit < 0) AS invalid_quotas,
        (SELECT count(*) FROM detection_threshold_config
         WHERE block_confidence IS NULL
            OR flag_confidence IS NULL
            OR NOT (0 <= flag_confidence
                    AND flag_confidence < block_confidence
                    AND block_confidence <= 1)) AS invalid_thresholds,
        (SELECT count(*) FROM source_database_connections
         WHERE database_type IS NULL
            OR database_type NOT IN ('postgresql', 'mysql', 'mssql')
            OR lifecycle_state IS NULL
            OR lifecycle_state NOT IN ('active', 'disabled')
            OR health_status IS NULL
            OR health_status NOT IN ('untested', 'healthy', 'unhealthy')
            OR schema_introspection_status IS NULL
            OR schema_introspection_status NOT IN ('none', 'success', 'failed', 'stale')) AS invalid_sources,
        (SELECT count(*) FROM users
         WHERE auth_provider IS NULL
            OR auth_provider NOT IN ('local', 'oidc', 'saml')) AS invalid_auth_providers,
        (SELECT count(*) FROM sso_providers
         WHERE protocol IS NULL
            OR protocol NOT IN ('oidc', 'saml')) AS invalid_sso_protocols
    """
)
_PREFLIGHT_LOCK_SQL = sa.text(
    """
    LOCK TABLE
        role_quotas,
        detection_threshold_config,
        source_database_connections,
        users,
        sso_providers
    IN SHARE ROW EXCLUSIVE MODE
    """
)


def _read_preflight_counts(connection) -> Mapping[str, int]:
    return connection.execute(_PREFLIGHT_SQL).mappings().one()


def _refuse_invalid_rows(counts: Mapping[str, int]) -> None:
    if any(int(count) for count in counts.values()):
        raise RuntimeError(_PREFLIGHT_REFUSAL)


def _run_preflight() -> None:
    connection = op.get_bind()
    _refuse_invalid_rows(_read_preflight_counts(connection))
    connection.execute(_PREFLIGHT_LOCK_SQL)
    _refuse_invalid_rows(_read_preflight_counts(connection))


def upgrade() -> None:
    _run_preflight()

    op.create_check_constraint(
        "ck_role_quotas_daily_query_limit_nonnegative",
        "role_quotas",
        "daily_query_limit IS NULL OR daily_query_limit >= 0",
    )
    op.create_check_constraint(
        "ck_role_quotas_daily_execution_limit_nonnegative",
        "role_quotas",
        "daily_execution_limit IS NULL OR daily_execution_limit >= 0",
    )
    op.create_check_constraint(
        "ck_role_quotas_daily_export_limit_nonnegative",
        "role_quotas",
        "daily_export_limit IS NULL OR daily_export_limit >= 0",
    )
    op.create_check_constraint(
        "ck_detection_thresholds_ordered_range",
        "detection_threshold_config",
        "0 <= flag_confidence AND flag_confidence < block_confidence AND block_confidence <= 1",
    )
    op.create_check_constraint(
        "ck_source_db_connections_database_type_valid",
        "source_database_connections",
        "database_type IN ('postgresql', 'mysql', 'mssql')",
    )
    op.create_check_constraint(
        "ck_source_db_connections_lifecycle_state_valid",
        "source_database_connections",
        "lifecycle_state IN ('active', 'disabled')",
    )
    op.create_check_constraint(
        "ck_source_db_connections_health_status_valid",
        "source_database_connections",
        "health_status IN ('untested', 'healthy', 'unhealthy')",
    )
    op.create_check_constraint(
        "ck_source_db_connections_schema_status_valid",
        "source_database_connections",
        "schema_introspection_status IN ('none', 'success', 'failed', 'stale')",
    )
    op.create_check_constraint(
        "ck_users_auth_provider_valid",
        "users",
        "auth_provider IN ('local', 'oidc', 'saml')",
    )
    op.create_check_constraint(
        "ck_sso_providers_protocol_valid",
        "sso_providers",
        "protocol IN ('oidc', 'saml')",
    )
    op.execute(
        sa.text(
            """
            INSERT INTO detection_threshold_config (block_confidence, flag_confidence)
            SELECT 0.8, 0.5
            WHERE NOT EXISTS (SELECT 1 FROM detection_threshold_config)
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint("ck_sso_providers_protocol_valid", "sso_providers", type_="check")
    op.drop_constraint("ck_users_auth_provider_valid", "users", type_="check")
    op.drop_constraint(
        "ck_source_db_connections_schema_status_valid",
        "source_database_connections",
        type_="check",
    )
    op.drop_constraint(
        "ck_source_db_connections_health_status_valid",
        "source_database_connections",
        type_="check",
    )
    op.drop_constraint(
        "ck_source_db_connections_lifecycle_state_valid",
        "source_database_connections",
        type_="check",
    )
    op.drop_constraint(
        "ck_source_db_connections_database_type_valid",
        "source_database_connections",
        type_="check",
    )
    op.drop_constraint(
        "ck_detection_thresholds_ordered_range",
        "detection_threshold_config",
        type_="check",
    )
    op.drop_constraint(
        "ck_role_quotas_daily_export_limit_nonnegative",
        "role_quotas",
        type_="check",
    )
    op.drop_constraint(
        "ck_role_quotas_daily_execution_limit_nonnegative",
        "role_quotas",
        type_="check",
    )
    op.drop_constraint(
        "ck_role_quotas_daily_query_limit_nonnegative",
        "role_quotas",
        type_="check",
    )
