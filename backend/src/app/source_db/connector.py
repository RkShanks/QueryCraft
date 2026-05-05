"""Source DB connector — read-only asyncpg pool.

T-104: SourceDBConnector creates and manages an asyncpg connection pool.
"""

from contextlib import asynccontextmanager

import asyncpg

from app.core.config import get_settings
from app.core.encryption import decrypt


class SourceDBConnector:
    """Manages a read-only connection pool to the source PostgreSQL database."""

    def __init__(self):
        self._pool: asyncpg.Pool | None = None

    async def init_pool(self) -> None:
        """Initialise the asyncpg pool from settings."""
        settings = get_settings()
        raw_password = settings.SOURCE_DB_PASSWORD
        try:
            password = decrypt(raw_password)
        except Exception:
            # If decryption fails, assume plaintext (dev mode)
            password = raw_password
        self._pool = await asyncpg.create_pool(
            host=settings.SOURCE_DB_HOST,
            port=settings.SOURCE_DB_PORT,
            database=settings.SOURCE_DB_NAME,
            user=settings.SOURCE_DB_USER,
            password=password,
            ssl="disable" if settings.SOURCE_DB_SSL_MODE == "disable" else "require",
            min_size=1,
            max_size=getattr(settings, "SOURCE_DB_POOL_SIZE", 5),
        )

    async def aclose(self) -> None:
        """Close the pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def get_connection(self):
        """Async context manager yielding a connection from the pool."""
        if self._pool is None:
            await self.init_pool()
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            yield conn
