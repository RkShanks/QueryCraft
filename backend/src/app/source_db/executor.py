"""Source DB executor — executes read-only SQL against the source database."""

import asyncio

import asyncpg

from app.core.config import get_settings


class SourceDBExecutor:
    """Execute SQL against the source PostgreSQL database."""

    def __init__(self):
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            settings = get_settings()
            self._pool = await asyncpg.create_pool(
                host=settings.SOURCE_DB_HOST,
                port=settings.SOURCE_DB_PORT,
                database=settings.SOURCE_DB_NAME,
                user=settings.SOURCE_DB_USER,
                password=settings.SOURCE_DB_PASSWORD,
                ssl="disable" if settings.SOURCE_DB_SSL_MODE == "disable" else "require",
                min_size=1,
                max_size=5,
            )
        return self._pool

    async def execute(self, sql: str, timeout: int = 30):
        """Execute SQL and return (columns, rows)."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await asyncio.wait_for(conn.fetch(sql), timeout=timeout)
            if not rows:
                return [], []
            columns = [{"name": k, "type": str(type(v).__name__)} for k, v in rows[0].items()]
            return columns, [list(r.values()) for r in rows]
