"""007_phase5_sso_rbac_security

Revision ID: 007
Revises: 006
Create Date: 2026-05-24

Phase 5 migration:
- Create sso_providers, roles, role_connection_policies, sso_group_mappings,
  user_identities, audit_log_entries tables
- Modify users table (add role_id, is_builtin, auth_provider; make password_hash nullable)
- Seed built-in admin role and genesis audit entry
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSIONS_JSON = json.dumps([
    "query.submit",
    "query.history.view",
    "admin.connections.manage",
    "admin.roles.manage",
    "admin.sso.manage",
    "admin.audit.verify",
])


def _make_genesis_hash() -> tuple[datetime, str]:
    """Compute the genesis audit entry row_hash using canonical JSON."""
    ts = datetime.now(timezone.utc)
    payload = {
        "sequence_number": 1,
        "timestamp": ts.isoformat(),
        "actor_id": None,
        "actor_identity": "system",
        "action_type": "admin.config.change",
        "resource_type": "audit",
        "resource_id": None,
        "outcome": "success",
        "context": {"note": "Phase 5 audit genesis"},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    row_hash = hashlib.sha256(f"{canonical}GENESIS".encode("utf-8")).hexdigest()
    return ts, row_hash


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Create new tables
    # ------------------------------------------------------------------
    op.create_table(
        "sso_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("protocol", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("issuer_url", sa.String(), nullable=True),
        sa.Column("client_id", sa.String(), nullable=True),
        sa.Column("encrypted_client_secret", sa.String(), nullable=True),
        sa.Column("scopes", sa.String(), nullable=True, server_default=sa.text("'openid email profile groups'")),
        sa.Column("redirect_uri", sa.String(), nullable=True),
        sa.Column("group_claim_name", sa.String(), nullable=False, server_default=sa.text("'groups'")),
        sa.Column("saml_entity_id", sa.String(), nullable=True),
        sa.Column("saml_metadata_url", sa.String(), nullable=True),
        sa.Column("encrypted_saml_metadata_xml", sa.Text(), nullable=True),
        sa.Column("encrypted_saml_certificate", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("protocol"),
    )

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("permissions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("priority"),
    )

    op.create_table(
        "role_connection_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allowed_tables", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("row_filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("column_masks", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["source_database_connections.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("role_id", "connection_id", name="uq_role_connection_policies_role_id_connection_id"),
    )

    op.create_table(
        "sso_group_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("sso_group_value", sa.String(), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("sso_group_value"),
    )

    op.create_table(
        "user_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("sso_groups", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("provider", "subject_id", name="uq_user_identities_provider_subject_id"),
    )

    op.create_table(
        "audit_log_entries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sequence_number", sa.BigInteger(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_identity", sa.String(), nullable=True),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("row_hash", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sequence_number"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_log_entries_timestamp", "audit_log_entries", ["timestamp"])
    op.create_index("ix_audit_log_entries_action_type", "audit_log_entries", ["action_type"])
    op.create_index("ix_audit_log_entries_actor_id", "audit_log_entries", ["actor_id"])

    # ------------------------------------------------------------------
    # 2. Modify users table
    # ------------------------------------------------------------------
    op.alter_column("users", "password_hash", nullable=True)
    op.add_column(
        "users",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "users",
        sa.Column("auth_provider", sa.String(), nullable=False, server_default=sa.text("'local'")),
    )
    op.create_foreign_key(
        "fk_users_role_id",
        "users",
        "roles",
        ["role_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ------------------------------------------------------------------
    # 3. Seed built-in admin role and update existing admin user
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            INSERT INTO roles (name, description, priority, permissions, is_builtin, created_at, updated_at)
            VALUES (
                'Admin',
                'Built-in administrator role',
                0,
                (:permissions)::jsonb,
                true,
                now(),
                now()
            )
            ON CONFLICT (name) DO NOTHING
            """
        ).bindparams(permissions=PERMISSIONS_JSON)
    )

    op.execute(
        sa.text(
            """
            UPDATE users
            SET role_id = roles.id,
                is_builtin = true,
                auth_provider = 'local'
            FROM roles
            WHERE roles.is_builtin = true
              AND (users.role_id IS NULL OR users.role = 'admin')
            """
        )
    )

    # ------------------------------------------------------------------
    # 4. Seed genesis audit log entry
    # ------------------------------------------------------------------
    genesis_ts, genesis_hash = _make_genesis_hash()
    op.execute(
        sa.text(
            """
            INSERT INTO audit_log_entries (
                sequence_number, timestamp, actor_identity, action_type,
                resource_type, outcome, context, prev_hash, row_hash
            )
            VALUES (
                1,
                :timestamp,
                'system',
                'admin.config.change',
                'audit',
                'success',
                (:context)::jsonb,
                'GENESIS',
                :row_hash
            )
            ON CONFLICT (sequence_number) DO NOTHING
            """
        ).bindparams(
            timestamp=genesis_ts,
            context=json.dumps({"note": "Phase 5 audit genesis"}),
            row_hash=genesis_hash,
        )
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_audit_log_entries_actor_id", table_name="audit_log_entries")
    op.drop_index("ix_audit_log_entries_action_type", table_name="audit_log_entries")
    op.drop_index("ix_audit_log_entries_timestamp", table_name="audit_log_entries")

    # Drop new tables in dependency order
    op.drop_table("audit_log_entries")
    op.drop_table("user_identities")
    op.drop_table("sso_group_mappings")
    op.drop_table("role_connection_policies")
    op.drop_table("sso_providers")

    # Restore users table
    op.drop_constraint("fk_users_role_id", "users", type_="foreignkey")
    op.drop_column("users", "auth_provider")
    op.drop_column("users", "is_builtin")
    op.drop_column("users", "role_id")
    op.alter_column("users", "password_hash", nullable=False)

    op.drop_table("roles")
