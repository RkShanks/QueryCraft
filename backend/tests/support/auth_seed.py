"""Shared test helpers for local admin auth setup."""

from __future__ import annotations

import json
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.security import hash_password
from app.db.models.enums import Permission


ADMIN_PERMISSIONS = [permission.value for permission in Permission]


async def sync_builtin_local_admin(conn: AsyncConnection) -> None:
    """Upsert the built-in local admin user and Admin role for auth tests."""
    username = os.environ.get("ADMIN_USERNAME", "admin")
    display_name = os.environ.get("ADMIN_DISPLAY_NAME", "Platform Administrator")
    password = os.environ.get("ADMIN_PASSWORD", "admin123")
    password_hash = hash_password(password)
    permissions_json = json.dumps(ADMIN_PERMISSIONS)

    role_result = await conn.execute(
        text(
            """
            INSERT INTO roles (name, description, priority, permissions, is_builtin)
            VALUES ('Admin', 'Built-in administrator role', 0, CAST(:permissions AS jsonb), true)
            ON CONFLICT (name)
            DO UPDATE SET
                description = EXCLUDED.description,
                priority = EXCLUDED.priority,
                permissions = EXCLUDED.permissions,
                is_builtin = true,
                updated_at = now()
            RETURNING id
            """
        ),
        {"permissions": permissions_json},
    )
    role_id = role_result.scalar_one()

    await conn.execute(
        text(
            """
            INSERT INTO users (username, display_name, password_hash, role, role_id, is_builtin, auth_provider)
            VALUES (:username, :display_name, :password_hash, 'admin', :role_id, true, 'local')
            ON CONFLICT (username)
            DO UPDATE SET
                display_name = EXCLUDED.display_name,
                password_hash = EXCLUDED.password_hash,
                role = 'admin',
                role_id = EXCLUDED.role_id,
                updated_at = now(),
                is_builtin = true,
                auth_provider = 'local'
            """
        ),
        {
            "username": username,
            "display_name": display_name,
            "password_hash": password_hash,
            "role_id": role_id,
        },
    )
