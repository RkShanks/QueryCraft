"""002 seed admin user — inserts the provisional admin account

Revision ID: 002
Revises: 001
Create Date: 2026-05-04
"""

import os
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Read admin credentials from environment
    username = os.environ.get("ADMIN_USERNAME")
    display_name = os.environ.get("ADMIN_DISPLAY_NAME")
    password = os.environ.get("ADMIN_PASSWORD")

    if not username or not display_name or not password:
        raise RuntimeError(
            "ADMIN_USERNAME, ADMIN_DISPLAY_NAME, and ADMIN_PASSWORD environment "
            "variables are required for the seed admin user migration."
        )

    # Hash the password with Argon2id
    from argon2 import PasswordHasher

    ph = PasswordHasher()
    password_hash = ph.hash(password)

    # Upsert admin user
    op.execute(
        f"""
        INSERT INTO users (username, display_name, password_hash, role)
        VALUES ('{username}', '{display_name}', '{password_hash}', 'admin')
        ON CONFLICT (username)
        DO UPDATE SET
            display_name = EXCLUDED.display_name,
            password_hash = EXCLUDED.password_hash,
            updated_at = now()
        """
    )


def downgrade() -> None:
    username = os.environ.get("ADMIN_USERNAME", "admin")
    op.execute(f"DELETE FROM users WHERE username = '{username}'")
