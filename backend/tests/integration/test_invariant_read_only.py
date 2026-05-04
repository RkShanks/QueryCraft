"""Invariant 5: Read-only source DB.

Attempts INSERT INTO against a test table in the source DB using a read-only role
and asserts PostgreSQL permission denied error.
"""

import asyncpg
import pytest


class TestReadOnlySourceDB:
    """Read-only source DB integration test."""

    @pytest.mark.asyncio
    async def test_insert_fails_with_read_only_role(self):
        """INSERT must fail at the database level for a read-only role."""
        # Connect as superuser to set up test table and read-only role
        conn = await asyncpg.connect(
            host="localhost",
            port=5434,
            database="source_analytics",
            user="source_readonly",
            password="source_dev",
        )
        try:
            # Create test table
            await conn.execute("CREATE TABLE IF NOT EXISTS invariant_test_table (id INT PRIMARY KEY)")
            # Ensure read-only role exists and has only SELECT
            await conn.execute(
                "DO $$ BEGIN CREATE ROLE testreadonly LOGIN PASSWORD 'readonly';"
                " EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
            )
            await conn.execute("GRANT CONNECT ON DATABASE source_analytics TO testreadonly")
            await conn.execute("GRANT USAGE ON SCHEMA public TO testreadonly")
            await conn.execute("GRANT SELECT ON invariant_test_table TO testreadonly")
            await conn.execute("REVOKE INSERT, UPDATE, DELETE ON invariant_test_table FROM testreadonly")
        finally:
            await conn.close()

        # Connect as read-only role and attempt INSERT
        ro_conn = await asyncpg.connect(
            host="localhost",
            port=5434,
            database="source_analytics",
            user="testreadonly",
            password="readonly",
        )
        try:
            with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
                await ro_conn.execute("INSERT INTO invariant_test_table VALUES (1)")
        finally:
            await ro_conn.close()
