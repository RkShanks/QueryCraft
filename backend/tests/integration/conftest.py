"""Shared fixtures for integration tests.

Provides table-isolation via TRUNCATE so ASGI-client commits from one
test don't leak into db_session-based tests.
"""

import pytest
from sqlalchemy import text

from tests.support.auth_seed import sync_builtin_local_admin


@pytest.fixture(autouse=True)
async def truncate_test_tables(async_engine_fixture, redis_client):
    """Reset all shared mutable state before every integration test.

    Necessary because integration tests use the ASGI test client
    (httpx.AsyncClient with ASGITransport), which commits real transactions
    through the FastAPI request lifecycle. These commits survive the
    db_session rollback and contaminate subsequent tests. Query quota and
    session state in Redis must be isolated for the same reason.

    Tables covered:
    - accepted_queries: written by POST /query/accept (router tests)
    - users: written by sign-up / sign-in flows (auth router tests)
    - role_quotas: written by quota administration flows
    - database_connections: written by admin connection management flows
    - app_config: written by admin config flows

    After truncation the seeded admin user is re-inserted so that
    authenticated_client can still sign in.
    """
    await redis_client.flushdb()
    async with async_engine_fixture.connect() as conn:
        await conn.execute(
            text(
                "TRUNCATE accepted_queries, sessions, users, role_quotas, "
                "source_database_connections, app_config "
                "RESTART IDENTITY CASCADE"
            )
        )
        await sync_builtin_local_admin(conn)
        await conn.commit()
