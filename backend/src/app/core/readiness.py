"""Bounded application lifecycle and dependency readiness checks."""

import asyncio
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

_PLATFORM_READINESS_QUERY = text("SELECT 1 AS probe_value, version_num FROM alembic_version LIMIT 2")


@lru_cache
def source_tree_alembic_head() -> str:
    """Return the source-tree head; the current database revision is never cached."""
    backend_root = Path(__file__).resolve().parents[3]
    alembic_ini = backend_root / "alembic.ini"
    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    head_revision = ScriptDirectory.from_config(config).get_current_head()
    if head_revision is None:
        raise RuntimeError("Alembic source tree has no head revision")
    return head_revision


class ReadinessState:
    """Track whether startup completed and shutdown has begun."""

    def __init__(
        self,
        engine_provider: Callable[[], AsyncEngine],
        redis_provider: Callable[[], Redis | None],
        expected_revision: str,
        deadline_seconds: float,
    ) -> None:
        self._engine_provider = engine_provider
        self._redis_provider = redis_provider
        self._expected_revision = expected_revision
        self._deadline_seconds = deadline_seconds
        self._probe_slot = asyncio.Semaphore(1)
        self._startup_complete = False
        self._shutdown_started = False

    @property
    def accepts_traffic(self) -> bool:
        return self._startup_complete and not self._shutdown_started

    def begin_startup(self) -> None:
        self._startup_complete = False
        self._shutdown_started = False

    def complete_startup(self) -> None:
        self._startup_complete = True

    def begin_shutdown(self) -> None:
        self._shutdown_started = True

    async def dependencies_ready(self) -> bool:
        """Return false for every dependency failure without exposing its details."""
        if not self.accepts_traffic:
            return False
        try:
            async with asyncio.timeout(self._deadline_seconds):
                async with self._probe_slot:
                    if not self.accepts_traffic:
                        return False
                    async with asyncio.TaskGroup() as probes:
                        database_probe = probes.create_task(self._platform_database_ready())
                        redis_probe = probes.create_task(self._redis_ready())
                    return self.accepts_traffic and database_probe.result() and redis_probe.result()
        except TimeoutError:
            return False
        except Exception:
            # Readiness is deliberately fail-closed for every dependency/client error.
            return False

    async def _platform_database_ready(self) -> bool:
        engine = self._engine_provider()
        async with engine.connect() as connection:
            connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
            query_rows = (await connection.execute(_PLATFORM_READINESS_QUERY)).all()
        normalized_rows = [tuple(row) for row in query_rows]
        return normalized_rows == [(1, self._expected_revision)]

    async def _redis_ready(self) -> bool:
        redis = self._redis_provider()
        return redis is not None and await redis.ping() is True
