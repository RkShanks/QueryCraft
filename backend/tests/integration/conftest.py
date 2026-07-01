"""Shared fixtures for integration tests.

Provides table-isolation via TRUNCATE so ASGI-client commits from one
test don't leak into db_session-based tests.
"""

import os

import pytest
from argon2 import PasswordHasher
from sqlalchemy import text


@pytest.fixture(autouse=True)
async def truncate_test_tables(async_engine_fixture):
    """Truncate all shared mutable tables before every integration test.

    Necessary because integration tests use the ASGI test client
    (httpx.AsyncClient with ASGITransport), which commits real transactions
    through the FastAPI request lifecycle. These commits survive the
    db_session rollback and contaminate subsequent tests.

    Tables covered:
    - accepted_queries: written by POST /query/accept (router tests)
    - users: written by sign-up / sign-in flows (auth router tests)
    - database_connections: written by admin connection management flows
    - app_config: written by admin config flows

    After truncation the seeded admin user is re-inserted so that
    authenticated_client can still sign in.
    """
    async with async_engine_fixture.connect() as conn:
        await conn.execute(
            text(
                "TRUNCATE accepted_queries, sessions, users, "
                "source_database_connections, app_config "
                "RESTART IDENTITY CASCADE"
            )
        )
        # Re-seed the admin user (required by authenticated_client fixture).
        # We resolve the Admin role UUID so that the session's permissions list
        # is populated correctly (role_obj loaded via role_id FK).
        username = os.environ.get("ADMIN_USERNAME", "admin")
        display_name = os.environ.get("ADMIN_DISPLAY_NAME", "Platform Administrator")
        password = os.environ.get("ADMIN_PASSWORD", "admin123")
        ph = PasswordHasher()
        password_hash = ph.hash(password)

        # Look up the Admin role id (case-insensitive match for robustness)
        role_result = await conn.execute(text("SELECT id FROM roles WHERE lower(name) = 'admin' LIMIT 1"))
        role_row = role_result.fetchone()
        role_id_clause = f"'{role_row[0]}'" if role_row else "NULL"

        await conn.execute(
            text(
                f"""
                INSERT INTO users (username, display_name, password_hash, role, role_id, is_builtin, auth_provider)
                VALUES ('{username}', '{display_name}', '{password_hash}', 'admin', {role_id_clause}, true, 'local')
                ON CONFLICT (username)
                DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    password_hash = EXCLUDED.password_hash,
                    role_id = EXCLUDED.role_id,
                    updated_at = now(),
                    is_builtin = true,
                    auth_provider = 'local'
                """
            )
        )
        await conn.commit()
