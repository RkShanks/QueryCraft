"""Source DB adapter protocol and per-dialect implementations (ADR-10, FR-069).

All adapters use parameterized queries only. No string interpolation.
"""

from typing import Any, Protocol

from app.core.credential_provider import CredentialProvider


class ExecuteResult:
    """Result of a parameterized query execution."""

    def __init__(self, columns: list[str], rows: list[tuple]) -> None:
        self.columns = columns
        self.rows = rows


class SourceDBAdapter(Protocol):
    """Protocol for source database adapters.

    Each dialect (PostgreSQL, MySQL, MSSQL) implements this interface.
    All queries MUST be parameterized — no string interpolation.
    """

    async def connect(self) -> None:
        """Establish a connection pool to the source database."""
        ...

    async def execute(self, sql: str, params: tuple = ()) -> ExecuteResult:
        """Execute a parameterized query and return results.

        Args:
            sql: Parameterized SQL query.
            params: Query parameters (positional).

        Returns:
            ExecuteResult with column names and row tuples.
        """
        ...

    async def health_check(self) -> bool:
        """Run a lightweight health check (SELECT 1 or dialect equivalent).

        Returns:
            True if the connection is healthy, False otherwise.
        """
        ...

    async def close(self) -> None:
        """Close the connection pool."""
        ...


class PostgresAdapter:
    """PostgreSQL adapter using asyncpg.

    Implements SourceDBAdapter protocol for PostgreSQL databases.
    Uses $1, $2, ... parameter placeholders (asyncpg native).
    """

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        username: str,
        encrypted_password: str,
        ssl_mode: str,
        credential_provider: CredentialProvider,
    ) -> None:
        self._host = host
        self._port = port
        self._database = database
        self._username = username
        self._encrypted_password = encrypted_password
        self._ssl_mode = ssl_mode
        self._credential_provider = credential_provider
        self._pool: Any = None

    async def connect(self) -> None:
        """Establish an asyncpg connection pool."""
        import asyncpg

        password = self._credential_provider.decrypt(self._encrypted_password)
        ssl = False if self._ssl_mode == "disable" else "require"
        self._pool = await asyncpg.create_pool(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._username,
            password=password,
            ssl=ssl,
            min_size=1,
            max_size=5,
        )

    async def execute(self, sql: str, params: tuple = ()) -> ExecuteResult:
        """Execute a parameterized query using asyncpg."""
        if self._pool is None:
            await self.connect()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            if not rows:
                return ExecuteResult(columns=[], rows=[])
            columns = list(rows[0].keys())
            row_tuples = [tuple(r.values()) for r in rows]
            return ExecuteResult(columns=columns, rows=row_tuples)

    async def health_check(self) -> bool:
        """Run SELECT 1 health check."""
        try:
            if self._pool is None:
                await self.connect()
            async with self._pool.acquire() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close the asyncpg pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
