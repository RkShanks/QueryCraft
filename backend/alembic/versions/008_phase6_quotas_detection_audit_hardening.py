"""008_phase6_quotas_detection_audit_hardening

Revision ID: 008
Revises: 007
Create Date: 2026-06-11
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "role_quotas",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("daily_query_limit", sa.Integer(), nullable=True),
        sa.Column("daily_execution_limit", sa.Integer(), nullable=True),
        sa.Column("daily_export_limit", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("role_id"),
    )

    op.create_table(
        "detection_threshold_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("block_confidence", sa.Float(), nullable=False, server_default=sa.text("0.8")),
        sa.Column("flag_confidence", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
    )

    op.execute(
        sa.text(
            """
            UPDATE roles
            SET permissions = (
                SELECT jsonb_agg(DISTINCT permission)
                FROM jsonb_array_elements_text(
                    permissions || '["admin.quotas.manage", "admin.security.manage"]'::jsonb
                ) AS permission
            ),
                updated_at = now()
            WHERE name = 'Admin' AND is_builtin = true
            """
        )
    )


def downgrade() -> None:
    op.drop_table("detection_threshold_config")
    op.drop_table("role_quotas")
