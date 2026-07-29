"""Run the audit-retention purge for an external scheduler."""

from __future__ import annotations

import asyncio
import logging

from app.db.base import dispose_engine, get_async_session_factory
from app.services.audit_service import AuditService

_LOGGER = logging.getLogger("querycraft.audit_purge")


async def _purge_once() -> int:
    """Purge once, committing the marker and deletions atomically."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            purged_count = await AuditService.purge_expired_entries(session)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    _LOGGER.info("Audit purge completed; purged_count=%d", purged_count)
    return purged_count


async def _run() -> int:
    try:
        await _purge_once()
    finally:
        await dispose_engine()
    return 0


def main() -> int:
    """Return a scheduler-friendly process exit code without leaking internals."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        return asyncio.run(_run())
    except Exception:
        _LOGGER.error("Audit purge failed safely; any active transaction was rolled back.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
