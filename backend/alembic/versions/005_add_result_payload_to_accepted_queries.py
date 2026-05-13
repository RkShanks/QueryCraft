"""005 add result payload to accepted_queries and seed max_regenerate_attempts

Revision ID: 005
Revises: 004
Create Date: 2026-05-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add result payload columns to accepted_queries
    op.add_column(
        "accepted_queries",
        sa.Column("result_columns", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "accepted_queries",
        sa.Column("result_rows", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "accepted_queries",
        sa.Column("result_row_count", sa.Integer(), nullable=True),
    )

    # Seed max_regenerate_attempts in app_config (default 3 = original + 2 regens)
    op.execute("""
        INSERT INTO app_config (key, value) VALUES
            ('max_regenerate_attempts', '3'::jsonb)
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_column("accepted_queries", "result_row_count")
    op.drop_column("accepted_queries", "result_rows")
    op.drop_column("accepted_queries", "result_columns")
