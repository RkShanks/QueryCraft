"""T-419: SourceDBAdapter protocol and PostgresAdapter tests.

Tests use mock connections to verify adapter contract compliance.
"""

from typing import Any

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
    from app.db.models.enums import DatabaseType
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
async def test_postgres_adapter_health_failure() -> None:
    """PostgresAdapter health check returns False on connection error."""
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

    result = await adapter.health_check()
    assert result is False
