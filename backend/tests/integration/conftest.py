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
        # Re-seed the admin user (required by authenticated_client fixture)
        username = os.environ.get("ADMIN_USERNAME", "admin")
        display_name = os.environ.get("ADMIN_DISPLAY_NAME", "Platform Administrator")
        password = os.environ.get("ADMIN_PASSWORD", "admin123")
        ph = PasswordHasher()
        password_hash = ph.hash(password)
        await conn.execute(
            text(
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
        )
        await conn.commit()
