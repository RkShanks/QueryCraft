"""T-419: SourceDBAdapter protocol and PostgresAdapter tests.

Tests use mock connections to verify adapter contract compliance.
"""

import asyncio
import secrets
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

# Valid Fernet key: 32 url-safe base64-encoded bytes
_VALID_FERNET_KEY = "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcyEhMTI="


class FakePGConnection:
    """Fake asyncpg-like connection for testing."""

    def __init__(self) -> None:
        self._closed = False
        self._fetch_calls: list[tuple[str, tuple]] = []
        self._execute_calls: list[str] = []
        self._fail_on: str | None = None

    async def fetch(self, query: str, *args: Any) -> list[dict]:
        if self._fail_on == "fetch":
            raise ConnectionError("fake fetch failure")
        self._fetch_calls.append((query, args))
        # Return a list of fake Record-like objects
        return [FakeRecord({"result": 1})]

    async def execute(self, query: str, *args: Any) -> str:
        if self._fail_on == "execute":
            raise ConnectionError("fake execute failure")
        self._execute_calls.append(query)
        return "SELECT 1"

    async def close(self) -> None:
        self._closed = True

    @property
    def is_closed(self) -> bool:
        return self._closed


class FakeRecord:
    """Fake asyncpg Record object."""

    def __init__(self, data: dict) -> None:
        self._data = data

    def keys(self) -> list[str]:
        return list(self._data.keys())

    def values(self) -> list:
        return list(self._data.values())

    def __iter__(self):
        return iter(self._data.keys())


class FakePGPool:
    """Fake asyncpg-like pool with async context manager support."""

    def __init__(self, conn: FakePGConnection) -> None:
        self._conn = conn
        self._closed = False

    def acquire(self) -> "FakePoolAcquireContext":
        return FakePoolAcquireContext(self._conn)

    async def close(self) -> None:
        self._closed = True

    @property
    def is_closed(self) -> bool:
        return self._closed


class FakePoolAcquireContext:
    """Async context manager for fake pool acquire."""

    def __init__(self, conn: FakePGConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> FakePGConnection:
        return self._conn

    async def __aexit__(self, *args: Any) -> None:
        pass


@pytest.mark.asyncio
async def test_postgres_adapter_connect_and_health() -> None:
    """PostgresAdapter connects and runs health check."""
    from app.core.credential_provider import FernetCredentialProvider
    from app.source_db.adapters import PostgresAdapter

    fake_conn = FakePGConnection()
    fake_pool = FakePGPool(fake_conn)

    credential_provider = FernetCredentialProvider(_VALID_FERNET_KEY)
    encrypted = credential_provider.encrypt("test_password")

    adapter = PostgresAdapter(
        host="localhost",
        port=5432,
        database="testdb",
        username="testuser",
        encrypted_password=encrypted,
        ssl_mode="disable",
        credential_provider=credential_provider,
    )
    adapter._pool = fake_pool

    result = await adapter.health_check()
    assert result is True
    assert fake_conn._execute_calls == ["SELECT 1"]


@pytest.mark.asyncio
async def test_postgres_adapter_execute_parameterized() -> None:
    """PostgresAdapter executes parameterized queries only."""
    from app.core.credential_provider import FernetCredentialProvider
    from app.source_db.adapters import PostgresAdapter

    fake_conn = FakePGConnection()
    fake_pool = FakePGPool(fake_conn)

    credential_provider = FernetCredentialProvider(_VALID_FERNET_KEY)
    encrypted = credential_provider.encrypt("test_password")

    adapter = PostgresAdapter(
        host="localhost",
        port=5432,
        database="testdb",
        username="testuser",
        encrypted_password=encrypted,
        ssl_mode="disable",
        credential_provider=credential_provider,
    )
    adapter._pool = fake_pool

    result = await adapter.execute("SELECT * FROM users WHERE id = $1", (1,))
    assert result.columns is not None
    assert result.rows is not None
    assert fake_conn._fetch_calls[0][0] == "SELECT * FROM users WHERE id = $1"


@pytest.mark.asyncio
async def test_postgres_adapter_close() -> None:
    """PostgresAdapter closes the pool."""
    from app.core.credential_provider import FernetCredentialProvider
    from app.source_db.adapters import PostgresAdapter

    fake_conn = FakePGConnection()
    fake_pool = FakePGPool(fake_conn)

    credential_provider = FernetCredentialProvider(_VALID_FERNET_KEY)
    encrypted = credential_provider.encrypt("test_password")

    adapter = PostgresAdapter(
        host="localhost",
        port=5432,
        database="testdb",
        username="testuser",
        encrypted_password=encrypted,
        ssl_mode="disable",
        credential_provider=credential_provider,
    )
    adapter._pool = fake_pool

    await adapter.close()
    assert fake_pool.is_closed


@pytest.mark.asyncio
async def test_postgres_adapter_health_failure_propagates_driver_error() -> None:
    """Driver failures reach the service for sanitized categorization."""
    from app.core.credential_provider import FernetCredentialProvider
    from app.source_db.adapters import PostgresAdapter

    fake_conn = FakePGConnection()
    fake_conn._fail_on = "execute"
    fake_pool = FakePGPool(fake_conn)

    credential_provider = FernetCredentialProvider(_VALID_FERNET_KEY)
    encrypted = credential_provider.encrypt("test_password")

    adapter = PostgresAdapter(
        host="localhost",
        port=5432,
        database="testdb",
        username="testuser",
        encrypted_password=encrypted,
        ssl_mode="disable",
        credential_provider=credential_provider,
    )
    adapter._pool = fake_pool

    with pytest.raises(ConnectionError, match="fake execute failure"):
        await adapter.health_check()


# ---------------------------------------------------------------------------
# T-420: MySQLAdapter tests
# ---------------------------------------------------------------------------


class FakeMySQLConnection:
    """Fake asyncmy-like connection for testing."""

    def __init__(self) -> None:
        self._closed = False
        self._fetch_calls: list[tuple[str, tuple]] = []
        self._execute_calls: list[str] = []
        self._fail_on: str | None = None
        self._cursor = FakeMySQLCursor(self)

    def cursor(self) -> "FakeMySQLCursor":
        return self._cursor

    def close(self) -> None:
        self._closed = True


class FakeMySQLCursor:
    """Fake asyncmy-like cursor."""

    def __init__(self, conn: FakeMySQLConnection) -> None:
        self._conn = conn
        self._rows: list[dict] = []
        self._description: list | None = None

    async def __aenter__(self) -> "FakeMySQLCursor":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def execute(self, query: str, *args: Any) -> int:
        if self._conn._fail_on == "execute":
            raise ConnectionError("fake execute failure")
        self._conn._execute_calls.append(query)
        self._rows = [{"result": 1}]
        self._description = [("result",)]
        return 1

    async def fetchall(self) -> list[tuple]:
        return [tuple(r.values()) for r in self._rows]

    @property
    def description(self) -> list | None:
        return self._description


class FakeMySQLPool:
    """Fake asyncmy-like pool.

    asyncmy.Pool.close() is synchronous; wait_closed() is async.
    """

    def __init__(self, conn: FakeMySQLConnection) -> None:
        self._conn = conn
        self._closed = False
        self._wait_closed_called = False

    def acquire(self) -> "FakeMySQLPoolAcquireContext":
        return FakeMySQLPoolAcquireContext(self._conn)

    def close(self) -> None:
        self._closed = True

    async def wait_closed(self) -> None:
        self._wait_closed_called = True

    @property
    def is_closed(self) -> bool:
        return self._closed


class FakeMySQLPoolAcquireContext:
    """Async context manager for fake MySQL pool acquire."""

    def __init__(self, conn: FakeMySQLConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> FakeMySQLConnection:
        return self._conn

    async def __aexit__(self, *args: Any) -> None:
        pass


@pytest.mark.asyncio
async def test_mysql_adapter_health_check() -> None:
    """MySQLAdapter runs health check using SELECT 1."""
    from app.core.credential_provider import FernetCredentialProvider
    from app.source_db.adapters import MySQLAdapter

    fake_conn = FakeMySQLConnection()
    fake_pool = FakeMySQLPool(fake_conn)

    credential_provider = FernetCredentialProvider(_VALID_FERNET_KEY)
    encrypted = credential_provider.encrypt("test_password")

    adapter = MySQLAdapter(
        host="localhost",
        port=3306,
        database="testdb",
        username="testuser",
        encrypted_password=encrypted,
        ssl_mode="disable",
        credential_provider=credential_provider,
    )
    adapter._pool = fake_pool

    result = await adapter.health_check()
    assert result is True
    assert fake_conn._execute_calls == ["SELECT 1"]


@pytest.mark.asyncio
async def test_mysql_adapter_execute_parameterized() -> None:
    """MySQLAdapter executes parameterized queries with %s placeholders."""
    from app.core.credential_provider import FernetCredentialProvider
    from app.source_db.adapters import MySQLAdapter

    fake_conn = FakeMySQLConnection()
    fake_pool = FakeMySQLPool(fake_conn)

    credential_provider = FernetCredentialProvider(_VALID_FERNET_KEY)
    encrypted = credential_provider.encrypt("test_password")

    adapter = MySQLAdapter(
        host="localhost",
        port=3306,
        database="testdb",
        username="testuser",
        encrypted_password=encrypted,
        ssl_mode="disable",
        credential_provider=credential_provider,
    )
    adapter._pool = fake_pool

    result = await adapter.execute("SELECT * FROM users WHERE id = %s", (1,))
    assert result.columns is not None
    assert result.rows is not None
    assert fake_conn._execute_calls == ["SELECT * FROM users WHERE id = %s"]


@pytest.mark.asyncio
async def test_mysql_adapter_close() -> None:
    """MySQLAdapter closes the pool."""
    from app.core.credential_provider import FernetCredentialProvider
    from app.source_db.adapters import MySQLAdapter

    fake_conn = FakeMySQLConnection()
    fake_pool = FakeMySQLPool(fake_conn)

    credential_provider = FernetCredentialProvider(_VALID_FERNET_KEY)
    encrypted = credential_provider.encrypt("test_password")

    adapter = MySQLAdapter(
        host="localhost",
        port=3306,
        database="testdb",
        username="testuser",
        encrypted_password=encrypted,
        ssl_mode="disable",
        credential_provider=credential_provider,
    )
    adapter._pool = fake_pool

    await adapter.close()
    assert fake_pool.is_closed
    assert fake_pool._wait_closed_called


# T-421: MSSQLAdapter tests
# ---------------------------------------------------------------------------


class FakeMSSQLConnection:
    """Fake aioodbc-like connection for testing."""

    def __init__(self) -> None:
        self._closed = False
        self._fetch_calls: list[tuple[str, tuple]] = []
        self._execute_calls: list[str] = []
        self._fail_on: str | None = None
        self._cursor = FakeMSSQLCursor(self)

    def cursor(self) -> "FakeMSSQLCursor":
        return self._cursor

    async def close(self) -> None:
        self._closed = True


class FakeMSSQLCursor:
    """Fake aioodbc-like cursor."""

    def __init__(self, conn: FakeMSSQLConnection) -> None:
        self._conn = conn
        self._impl = SimpleNamespace(timeout=0)
        self._rows: list[dict] = []
        self._description: list | None = None

    async def __aenter__(self) -> "FakeMSSQLCursor":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def execute(self, query: str, *params: Any) -> None:
        if self._conn._fail_on == "execute":
            raise ConnectionError("fake execute failure")
        self._conn._execute_calls.append((query, params))
        self._rows = [{"result": 1}]
        self._description = [("result",)]

    async def fetchall(self) -> list[tuple]:
        return [tuple(r.values()) for r in self._rows]

    @property
    def description(self) -> list | None:
        return self._description

    async def close(self) -> None:
        pass


class FakeMSSQLPool:
    """Fake aioodbc-like connection pool.

    aioodbc.Pool.close() is synchronous; wait_closed() is async.
    """

    def __init__(self, conn: FakeMSSQLConnection) -> None:
        self._conn = conn
        self._closed = False
        self._wait_closed_called = False

    def acquire(self) -> "FakeMSSQLPoolAcquireContext":
        return FakeMSSQLPoolAcquireContext(self._conn)

    def close(self) -> None:
        self._closed = True

    async def wait_closed(self) -> None:
        self._wait_closed_called = True

    @property
    def is_closed(self) -> bool:
        return self._closed


class FakeMSSQLPoolAcquireContext:
    """Async context manager for fake MSSQL pool acquire."""

    def __init__(self, conn: FakeMSSQLConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> FakeMSSQLConnection:
        return self._conn

    async def __aexit__(self, *args: Any) -> None:
        pass


@pytest.mark.asyncio
async def test_mssql_adapter_health_check() -> None:
    """MSSQLAdapter runs health check using SELECT 1."""
    from app.core.credential_provider import FernetCredentialProvider
    from app.source_db.adapters import MSSQLAdapter

    fake_conn = FakeMSSQLConnection()
    fake_pool = FakeMSSQLPool(fake_conn)

    credential_provider = FernetCredentialProvider(_VALID_FERNET_KEY)
    encrypted = credential_provider.encrypt("test_password")

    adapter = MSSQLAdapter(
        host="localhost",
        port=1433,
        database="testdb",
        username="testuser",
        encrypted_password=encrypted,
        ssl_mode="disable",
        credential_provider=credential_provider,
    )
    adapter._pool = fake_pool

    result = await adapter.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_mssql_adapter_execute_parameterized() -> None:
    """MSSQLAdapter executes parameterized queries with ? placeholders."""
    from app.core.credential_provider import FernetCredentialProvider
    from app.source_db.adapters import MSSQLAdapter

    fake_conn = FakeMSSQLConnection()
    fake_pool = FakeMSSQLPool(fake_conn)

    credential_provider = FernetCredentialProvider(_VALID_FERNET_KEY)
    encrypted = credential_provider.encrypt("test_password")

    adapter = MSSQLAdapter(
        host="localhost",
        port=1433,
        database="testdb",
        username="testuser",
        encrypted_password=encrypted,
        ssl_mode="disable",
        credential_provider=credential_provider,
    )
    adapter._pool = fake_pool

    result = await adapter.execute("SELECT * FROM users WHERE id = ?", (1,))
    assert result.columns is not None
    assert result.rows is not None


@pytest.mark.asyncio
async def test_mssql_adapter_close() -> None:
    """MSSQLAdapter closes the pool."""
    from app.core.credential_provider import FernetCredentialProvider
    from app.source_db.adapters import MSSQLAdapter

    fake_conn = FakeMSSQLConnection()
    fake_pool = FakeMSSQLPool(fake_conn)

    credential_provider = FernetCredentialProvider(_VALID_FERNET_KEY)
    encrypted = credential_provider.encrypt("test_password")

    adapter = MSSQLAdapter(
        host="localhost",
        port=1433,
        database="testdb",
        username="testuser",
        encrypted_password=encrypted,
        ssl_mode="disable",
        credential_provider=credential_provider,
    )
    adapter._pool = fake_pool

    await adapter.close()
    assert fake_pool.is_closed
    assert fake_pool._wait_closed_called


_ADAPTER_CASES = [
    pytest.param("PostgresAdapter", FakePGConnection, FakePGPool, 5432, id="postgres"),
    pytest.param("MySQLAdapter", FakeMySQLConnection, FakeMySQLPool, 3306, id="mysql"),
    pytest.param("MSSQLAdapter", FakeMSSQLConnection, FakeMSSQLPool, 1433, id="mssql"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("adapter_cls_name", "connection_cls", "pool_cls", "port"),
    _ADAPTER_CASES,
)
async def test_query_execution_timeout_cancels_each_dialect_adapter(
    adapter_cls_name: str,
    connection_cls: type,
    pool_cls: type,
    port: int,
) -> None:
    """The remaining operation budget bounds PostgreSQL, MySQL, and MSSQL."""
    from app.core.credential_provider import FernetCredentialProvider
    from app.core.exceptions import SourceDBTimeout
    from app.source_db import adapters

    fake_conn = connection_cls()

    if isinstance(fake_conn, FakeMSSQLConnection):
        fake_conn._cursor.execute = AsyncMock(side_effect=RuntimeError("HYT00", "driver timeout"))
        credential_provider = FernetCredentialProvider(_VALID_FERNET_KEY)
        adapter_cls = getattr(adapters, adapter_cls_name)
        adapter = adapter_cls(
            host="localhost",
            port=port,
            database="testdb",
            username="testuser",
            encrypted_password=credential_provider.encrypt("test_password"),
            ssl_mode="disable",
            credential_provider=credential_provider,
        )
        adapter._pool = pool_cls(fake_conn)

        with pytest.raises(SourceDBTimeout):
            await adapter.execute("SELECT id FROM users", timeout=2.9)

        assert fake_conn._cursor._impl.timeout == 2
        return

    execution_cancelled = asyncio.Event()

    async def slow_execution(*_args, **_kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            execution_cancelled.set()

    if isinstance(fake_conn, FakePGConnection):
        fake_conn.fetch = slow_execution
    else:
        fake_conn._cursor.execute = slow_execution

    credential_provider = FernetCredentialProvider(_VALID_FERNET_KEY)
    adapter_cls = getattr(adapters, adapter_cls_name)
    adapter = adapter_cls(
        host="localhost",
        port=port,
        database="testdb",
        username="testuser",
        encrypted_password=credential_provider.encrypt("test_password"),
        ssl_mode="disable",
        credential_provider=credential_provider,
    )
    adapter._pool = pool_cls(fake_conn)

    with pytest.raises(SourceDBTimeout):
        await adapter.execute("SELECT id FROM users", timeout=0.01)

    assert execution_cancelled.is_set()
    if isinstance(fake_conn, FakeMySQLConnection):
        assert fake_conn._closed


@pytest.mark.asyncio
async def test_mssql_external_cancellation_waits_for_driver_task_cleanup() -> None:
    """Session deletion must not abandon or cancel an in-flight ODBC worker."""
    from app.core.credential_provider import FernetCredentialProvider
    from app.source_db.adapters import MSSQLAdapter

    entered = asyncio.Event()
    release = asyncio.Event()
    driver_cancelled = asyncio.Event()
    fake_conn = FakeMSSQLConnection()

    async def controlled_execution(*_args, **_kwargs):
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            driver_cancelled.set()
            raise

    fake_conn._cursor.execute = controlled_execution
    credential_provider = FernetCredentialProvider(_VALID_FERNET_KEY)
    adapter = MSSQLAdapter(
        host="localhost",
        port=1433,
        database="testdb",
        username="testuser",
        encrypted_password=credential_provider.encrypt("test_password"),
        ssl_mode="disable",
        credential_provider=credential_provider,
    )
    adapter._pool = FakeMSSQLPool(fake_conn)

    operation = asyncio.create_task(adapter.execute("SELECT id FROM users", timeout=2.9))
    await entered.wait()
    operation.cancel()
    await asyncio.sleep(0)

    assert not driver_cancelled.is_set()
    assert not operation.done()

    release.set()
    with pytest.raises(asyncio.CancelledError):
        await operation


def _adapter_with_execution_error(
    adapter_cls_name: str,
    connection_cls: type,
    pool_cls: type,
    port: int,
    raised_error: BaseException,
):
    from app.core.credential_provider import FernetCredentialProvider
    from app.source_db import adapters

    fake_conn = connection_cls()
    if isinstance(fake_conn, FakePGConnection):
        fake_conn.fetch = AsyncMock(side_effect=raised_error)
    else:
        fake_conn._cursor.execute = AsyncMock(side_effect=raised_error)

    credential_provider = FernetCredentialProvider(_VALID_FERNET_KEY)
    adapter_cls = getattr(adapters, adapter_cls_name)
    adapter = adapter_cls(
        host="localhost",
        port=port,
        database="testdb",
        username="testuser",
        encrypted_password=credential_provider.encrypt("test_password"),
        ssl_mode="disable",
        credential_provider=credential_provider,
    )
    adapter._pool = pool_cls(fake_conn)
    return adapter


async def _captured_adapter_error(adapter) -> BaseException:
    try:
        await adapter.execute("SELECT id FROM users")
    except BaseException as exc:
        return exc
    pytest.fail("source adapter execution unexpectedly succeeded")


def _source_control_flow_error(source_error_name: str) -> BaseException:
    from app.core.exceptions import (
        SourceDBConnectionFailed,
        SourceDBPermissionDenied,
        SourceDBTimeout,
    )

    source_errors = {
        "timeout": TimeoutError(),
        "source_timeout": SourceDBTimeout(timeout_seconds=30),
        "permission_denied": SourceDBPermissionDenied(),
        "connection_failed": SourceDBConnectionFailed(),
        "cancelled": asyncio.CancelledError(),
    }
    return source_errors[source_error_name]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("adapter_cls_name", "connection_cls", "pool_cls", "port"),
    _ADAPTER_CASES,
)
async def test_adapter_execution_failure_is_sanitized(
    adapter_cls_name: str,
    connection_cls: type,
    pool_cls: type,
    port: int,
) -> None:
    """XP-007: source adapters never expose raw driver details."""
    from app.core.exceptions import SourceDBExecutionFailed

    driver_probe = secrets.token_urlsafe(18)
    adapter = _adapter_with_execution_error(
        adapter_cls_name,
        connection_cls,
        pool_cls,
        port,
        RuntimeError(driver_probe),
    )

    caught_error = await _captured_adapter_error(adapter)

    if not isinstance(caught_error, SourceDBExecutionFailed):
        pytest.fail(f"unexpected execution error type: {type(caught_error).__name__}")
    assert driver_probe not in str(caught_error)
    assert caught_error.__cause__ is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("adapter_cls_name", "connection_cls", "pool_cls", "port"),
    _ADAPTER_CASES,
)
@pytest.mark.parametrize(
    "source_error_name",
    [
        pytest.param("timeout", id="TimeoutError"),
        pytest.param("source_timeout", id="SourceDBTimeout"),
        pytest.param("permission_denied", id="SourceDBPermissionDenied"),
        pytest.param("connection_failed", id="SourceDBConnectionFailed"),
        pytest.param("cancelled", id="CancelledError"),
    ],
)
async def test_adapter_execution_preserves_typed_control_flow_errors(
    adapter_cls_name: str,
    connection_cls: type,
    pool_cls: type,
    port: int,
    source_error_name: str,
) -> None:
    """XP-007: timeout, cancellation, and typed source errors keep their contract."""
    raised_error = _source_control_flow_error(source_error_name)
    adapter = _adapter_with_execution_error(
        adapter_cls_name,
        connection_cls,
        pool_cls,
        port,
        raised_error,
    )

    caught_error = await _captured_adapter_error(adapter)

    assert caught_error is raised_error
