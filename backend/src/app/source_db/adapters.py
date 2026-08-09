"""Source DB adapter protocol and per-dialect implementations (ADR-10, FR-069).

All adapters use parameterized queries only. No string interpolation.
"""

import asyncio
import math
from contextlib import asynccontextmanager, suppress
from typing import Any, Protocol

from app.core.credential_provider import CredentialProvider
from app.core.exceptions import SourceDBError, SourceDBExecutionFailed, SourceDBTimeout


@asynccontextmanager
async def _execution_timeout(timeout: float | None):
    try:
        async with asyncio.timeout(timeout):
            yield
    except TimeoutError as exc:
        if timeout is None:
            raise
        raise SourceDBTimeout(timeout_seconds=math.ceil(timeout)) from exc


def _mssql_driver_timeout(timeout: float | None) -> int:
    """Return a whole-second ODBC timeout that expires before the budget."""
    if timeout is None:
        return 0
    if not math.isfinite(timeout) or timeout <= 0:
        raise SourceDBTimeout(timeout_seconds=1)
    driver_timeout = math.floor(timeout)
    if driver_timeout < 1:
        raise SourceDBTimeout(timeout_seconds=1)
    return driver_timeout


def _is_mssql_timeout(error: BaseException) -> bool:
    return any(str(arg).upper().startswith(("HYT00", "HYT01")) for arg in error.args)


async def _drain_shielded(task: asyncio.Task[Any]) -> None:
    """Wait for an ODBC worker without forwarding cancellation into its thread."""
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
        except Exception:
            break
    with suppress(asyncio.CancelledError, Exception):
        task.result()


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

    async def execute(
        self,
        sql: str,
        params: tuple = (),
        *,
        timeout: float | None = None,
    ) -> ExecuteResult:
        """Execute a parameterized query and return results.

        Args:
            sql: Parameterized SQL query.
            params: Query parameters (positional).
            timeout: Remaining query-operation budget. ``None`` is reserved
                for non-query callers such as schema introspection.

        Returns:
            ExecuteResult with column names and row tuples.
        """
        ...

    async def health_check(self) -> bool:
        """Run a lightweight health check (SELECT 1 or dialect equivalent).

        Returns:
            True if the connection is healthy.

        Raises:
            Exception: Source-driver failures for the connection service to
                classify into a sanitized health status.
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

    async def execute(
        self,
        sql: str,
        params: tuple = (),
        *,
        timeout: float | None = None,
    ) -> ExecuteResult:
        """Execute a parameterized query using asyncpg."""
        try:
            async with _execution_timeout(timeout):
                if self._pool is None:
                    await self.connect()
                async with self._pool.acquire() as conn:
                    rows = await conn.fetch(sql, *params)
                    if not rows:
                        return ExecuteResult(columns=[], rows=[])
                    columns = [c.lower() for c in rows[0].keys()]  # noqa: SIM118
                    row_tuples = [tuple(r.values()) for r in rows]
                    return ExecuteResult(columns=columns, rows=row_tuples)
        except (TimeoutError, SourceDBError):
            raise
        except Exception:
            raise SourceDBExecutionFailed() from None

    async def health_check(self) -> bool:
        """Run SELECT 1 health check."""
        if self._pool is None:
            await self.connect()
        async with self._pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return True

    async def close(self) -> None:
        """Close the asyncpg pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


class MySQLAdapter:
    """MySQL adapter using asyncmy.

    Implements SourceDBAdapter protocol for MySQL databases.
    Uses %s parameter placeholders (MySQL native).
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
        """Establish an asyncmy connection pool."""
        import asyncmy

        password = self._credential_provider.decrypt(self._encrypted_password)
        ssl = {} if self._ssl_mode == "disable" else {"ssl": True}
        self._pool = await asyncmy.create_pool(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._username,
            password=password,
            minsize=1,
            maxsize=5,
            **ssl,
        )

    async def execute(
        self,
        sql: str,
        params: tuple = (),
        *,
        timeout: float | None = None,
    ) -> ExecuteResult:
        """Execute a parameterized query using asyncmy."""
        connection = None
        try:
            async with _execution_timeout(timeout):
                if self._pool is None:
                    await self.connect()
                async with self._pool.acquire() as connection:
                    try:
                        async with connection.cursor() as cursor:
                            await cursor.execute(sql, params)
                            rows = await cursor.fetchall()
                            if not rows:
                                return ExecuteResult(columns=[], rows=[])
                            columns = [d[0].lower() for d in cursor.description] if cursor.description else []
                            row_tuples = [tuple(r) for r in rows]
                            return ExecuteResult(columns=columns, rows=row_tuples)
                    except asyncio.CancelledError:
                        connection.close()
                        raise
        except (asyncio.CancelledError, SourceDBTimeout):
            if connection is not None:
                connection.close()
            if self._pool is not None:
                self._pool.close()
                await self._pool.wait_closed()
                self._pool = None
            raise
        except (TimeoutError, SourceDBError):
            raise
        except Exception:
            raise SourceDBExecutionFailed() from None

    async def health_check(self) -> bool:
        """Run SELECT 1 health check."""
        if self._pool is None:
            await self.connect()
        async with self._pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute("SELECT 1")
        return True

    async def close(self) -> None:
        """Close the asyncmy pool.

        asyncmy.Pool.close() is synchronous; must await wait_closed().
        """
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None


class MSSQLAdapter:
    """MSSQL adapter using aioodbc.

    Implements SourceDBAdapter protocol for Microsoft SQL Server.
    Uses ? parameter placeholders (ODBC native).
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

    async def connect(self, timeout: int = 0) -> None:
        """Establish an aioodbc connection pool."""
        import aioodbc

        password = self._credential_provider.decrypt(self._encrypted_password)
        conn_str = (
            f"DRIVER={{FreeTDS}};"
            f"SERVER={self._host},{self._port};"
            f"DATABASE={self._database};"
            f"UID={self._username};"
            f"PWD={password};"
            f"TDS_Version=7.4;"
        )
        self._pool = await aioodbc.create_pool(
            dsn=conn_str,
            minsize=1,
            maxsize=5,
            timeout=timeout,
        )

    async def execute(
        self,
        sql: str,
        params: tuple = (),
        *,
        timeout: float | None = None,
    ) -> ExecuteResult:
        """Execute a parameterized query using aioodbc."""
        driver_timeout = _mssql_driver_timeout(timeout)

        async def run_query() -> ExecuteResult:
            if self._pool is None:
                await self.connect(timeout=driver_timeout)
            async with self._pool.acquire() as conn:
                conn._conn.timeout = driver_timeout
                async with conn.cursor() as cur:
                    await cur.execute(sql, params)
                    rows = await cur.fetchall()
                    if not rows:
                        return ExecuteResult(columns=[], rows=[])
                    columns = [d[0].lower() for d in cur.description] if cur.description else []
                    row_tuples = [tuple(r) for r in rows]
                    return ExecuteResult(columns=columns, rows=row_tuples)

        execution_task: asyncio.Task[ExecuteResult] | None = None
        try:
            if timeout is None:
                return await run_query()
            execution_task = asyncio.create_task(run_query())
            return await asyncio.shield(execution_task)
        except asyncio.CancelledError:
            if execution_task is not None:
                await _drain_shielded(execution_task)
            raise
        except (TimeoutError, SourceDBError):
            raise
        except Exception as exc:
            if _is_mssql_timeout(exc):
                raise SourceDBTimeout(timeout_seconds=driver_timeout) from exc
            raise SourceDBExecutionFailed() from None

    async def health_check(self) -> bool:
        """Run SELECT 1 health check."""
        if self._pool is None:
            await self.connect()
        async with self._pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("SELECT 1")
        return True

    async def close(self) -> None:
        """Close the aioodbc pool.

        aioodbc.Pool.close() is synchronous; must await wait_closed().
        """
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
