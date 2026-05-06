"""T-122: Invariant 5 — Read-only source DB (strengthened to real app connection).

Tests that the SourceDBConnector (using pagila_user from app config) cannot
execute data-modifying statements. Also keeps the legacy testreadonly regression
path.
"""

import asyncpg
import pytest

from app.source_db.connector import SourceDBConnector


class TestReadOnlySourceDB:
    """Read-only source DB integration test."""

    @pytest.mark.asyncio
    async def test_select_succeeds_with_app_connector(self):
        """SELECT must succeed via the real app SourceDBConnector."""
        connector = SourceDBConnector()
        async with connector.get_connection() as conn:
            result = await conn.fetch("SELECT * FROM actor LIMIT 1")
            assert len(result) == 1
        await connector.aclose()

    @pytest.mark.asyncio
    async def test_insert_fails_with_app_connector(self):
        """INSERT must fail at the database level for the app connector role."""
        connector = SourceDBConnector()
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            async with connector.get_connection() as conn:
                await conn.execute("INSERT INTO actor (first_name, last_name) VALUES ('X', 'Y')")
        await connector.aclose()

    @pytest.mark.asyncio
    async def test_update_fails_with_app_connector(self):
        """UPDATE must fail at the database level."""
        connector = SourceDBConnector()
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            async with connector.get_connection() as conn:
                await conn.execute("UPDATE actor SET first_name = 'X' WHERE actor_id = 1")
        await connector.aclose()

    @pytest.mark.asyncio
    async def test_delete_fails_with_app_connector(self):
        """DELETE must fail at the database level."""
        connector = SourceDBConnector()
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            async with connector.get_connection() as conn:
                await conn.execute("DELETE FROM actor WHERE actor_id = 1")
        await connector.aclose()

    @pytest.mark.asyncio
    async def test_truncate_fails_with_app_connector(self):
        """TRUNCATE must fail at the database level."""
        connector = SourceDBConnector()
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            async with connector.get_connection() as conn:
                await conn.execute("TRUNCATE actor")
        await connector.aclose()

    @pytest.mark.asyncio
    async def test_drop_fails_with_app_connector(self):
        """DROP must fail at the database level."""
        connector = SourceDBConnector()
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            async with connector.get_connection() as conn:
                await conn.execute("DROP TABLE actor")
        await connector.aclose()

    @pytest.mark.asyncio
    async def test_create_fails_with_app_connector(self):
        """CREATE must fail at the database level for the app connector role.

        The container bootstrap superuser (source_readonly) must NOT match the
        app's SOURCE_DB_USER (pagila_user). With correct separation, pagila_user
        has no CREATE privilege.
        """
        connector = SourceDBConnector()
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            async with connector.get_connection() as conn:
                await conn.execute("CREATE TABLE test_table_inv5 (id INT)")
        await connector.aclose()

    @pytest.mark.asyncio
    async def test_insert_fails_with_read_only_role_legacy(self):
        """INSERT must fail at the database level for a read-only role (legacy regression)."""
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
