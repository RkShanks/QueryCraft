"""Source DB executor — executes read-only SQL against the source database.

T-106: Full rewrite of SourceDBExecutor.
- Accepts SourceDBConnector via constructor.
- Sets postgres statement_timeout for defence-in-depth.
- Uses asyncio.wait_for for client-side timeout.
- Wraps errors in typed exceptions.
"""

import asyncio
from typing import Any

import asyncpg

from app.core.exceptions import (
    SourceDBConnectionFailed,
    SourceDBPermissionDenied,
    SourceDBTimeout,
)
from app.source_db.connector import SourceDBConnector


class SourceDBExecutor:
    """Execute SQL against the source PostgreSQL database."""

    def __init__(self, connector: SourceDBConnector):
        self._connector = connector

    async def execute(
        self,
        sql: str,
        timeout: float = 30.0,
        params: tuple[Any, ...] = (),
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Execute *sql* and return (column_names, rows).

        Args:
            sql: Parameterized SQL with ``$N`` placeholders.
            timeout: Client-side timeout in seconds.
            params: Positional parameter values for the ``$N`` placeholders.
                Empty tuple means no parameters. asyncpg is positional so
                the order matters (T-712 row-filter integration).

        Raises:
            SourceDBTimeout: on client- or server-side timeout.
            SourceDBPermissionDenied: on insufficient privileges.
            SourceDBConnectionFailed: on connection errors.
        """
        try:
            async with self._connector.get_connection() as conn:
                # Defence-in-depth: set postgres-side statement timeout
                timeout_ms = int(timeout * 1000)
                await conn.execute(f"SET LOCAL statement_timeout = '{timeout_ms}ms'")

                try:
                    rows = await asyncio.wait_for(
                        conn.fetch(sql, *params) if params else conn.fetch(sql),
                        timeout=timeout,
                    )
                except TimeoutError as exc:
                    raise SourceDBTimeout(timeout_seconds=int(timeout)) from exc
                except asyncpg.exceptions.QueryCanceledError as exc:
                    raise SourceDBTimeout(timeout_seconds=int(timeout)) from exc
                except asyncpg.exceptions.InsufficientPrivilegeError as exc:
                    raise SourceDBPermissionDenied() from exc

                if not rows:
                    return [], []

                columns = list(rows[0].keys())
                row_tuples = [tuple(r.values()) for r in rows]
                return columns, row_tuples

        except (SourceDBTimeout, SourceDBPermissionDenied):
            raise
        except asyncpg.exceptions.ConnectionDoesNotExistError as exc:
            raise SourceDBConnectionFailed() from exc
        except asyncpg.exceptions.InterfaceError as exc:
            raise SourceDBConnectionFailed() from exc
        except Exception:
            # Re-raise unknown exceptions for now; can be refined later
            raise
