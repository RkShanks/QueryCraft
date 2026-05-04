"""Shared fixtures for integration tests.

Provides table-isolation via TRUNCATE so ASGI-client commits from one
test don't leak into db_session-based tests.
"""

import pytest
from sqlalchemy import text


@pytest.fixture(autouse=True)
async def truncate_test_tables(async_engine_fixture):
    """Truncate mutable test tables before every integration test."""
    async with async_engine_fixture.connect() as conn:
        await conn.execute(text("TRUNCATE accepted_queries RESTART IDENTITY CASCADE"))
        await conn.commit()
