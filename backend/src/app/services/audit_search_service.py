"""AuditSearchService — filtered, paginated, retention-enforced audit log search.

T-860.

Constraints (from tasks.md and orchestration-log.md):
- Enforces retention window server-side BEFORE pagination (WHERE timestamp >= cutoff).
- All WHERE clauses use SQLAlchemy ORM expressions — no raw SQL strings.
- Default sort: timestamp DESC.
- Returns AuditSearchResponse with entries list and pagination metadata.
- Search never logs returned entry values.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log_entry import AuditLogEntry
from app.schemas.audit_search import AuditEntryRead, AuditSearchPagination, AuditSearchParams, AuditSearchResponse

try:
    from dateutil.relativedelta import relativedelta
except ImportError:  # pragma: no cover
    relativedelta = None  # type: ignore[assignment]


class AuditSearchService:
    """Filtered + paginated audit log search with server-side retention enforcement."""

    @staticmethod
    def _retention_cutoff(retention_months: int) -> datetime:
        """Compute the earliest timestamp to include (entries must be >= cutoff)."""
        now = datetime.now(UTC)
        if relativedelta is not None:
            return now - relativedelta(months=retention_months)
        return now - timedelta(days=retention_months * 30)

    @classmethod
    async def search(
        cls,
        session: AsyncSession,
        params: AuditSearchParams,
        retention_months: int,
    ) -> AuditSearchResponse:
        """Search audit entries with filters, retention window, and pagination.

        Parameters
        ----------
        session:
            Async SQLAlchemy session.
        params:
            Search filter and pagination parameters.
        retention_months:
            Retention window size. Entries older than this are excluded
            server-side before pagination.

        Returns
        -------
        AuditSearchResponse
            Paginated list of matching entries plus pagination metadata.
        """
        cutoff = cls._retention_cutoff(retention_months)

        # Base filter: always enforce retention window
        base_filters = [AuditLogEntry.timestamp >= cutoff]

        # Optional caller filters
        if params.action_type is not None:
            base_filters.append(AuditLogEntry.action_type == params.action_type)
        if params.actor_identity is not None:
            base_filters.append(AuditLogEntry.actor_identity == params.actor_identity)
        if params.outcome is not None:
            base_filters.append(AuditLogEntry.outcome == params.outcome)
        if params.resource_type is not None:
            base_filters.append(AuditLogEntry.resource_type == params.resource_type)
        if params.start_date is not None:
            base_filters.append(AuditLogEntry.timestamp >= params.start_date)
        if params.end_date is not None:
            base_filters.append(AuditLogEntry.timestamp <= params.end_date)

        # Count total matching rows (for pagination metadata)
        count_query = select(func.count()).select_from(AuditLogEntry).where(*base_filters)
        count_result = await session.execute(count_query)
        total_entries = int(count_result.scalar_one())

        # Paginated data query — default sort: timestamp DESC
        offset = (params.page - 1) * params.page_size
        data_query = (
            select(AuditLogEntry)
            .where(*base_filters)
            .order_by(AuditLogEntry.timestamp.desc())
            .offset(offset)
            .limit(params.page_size)
        )
        rows_result = await session.execute(data_query)
        rows = rows_result.scalars().all()

        total_pages = max(1, math.ceil(total_entries / params.page_size)) if total_entries > 0 else 1

        entries = [_row_to_read(row) for row in rows]

        return AuditSearchResponse(
            entries=entries,
            pagination=AuditSearchPagination(
                page=params.page,
                page_size=params.page_size,
                total_entries=total_entries,
                total_pages=total_pages,
            ),
        )


def _row_to_read(row: Any) -> AuditEntryRead:
    """Convert an AuditLogEntry ORM row to AuditEntryRead schema."""
    return AuditEntryRead(
        sequence_number=row.sequence_number,
        timestamp=row.timestamp,
        actor_identity=row.actor_identity,
        action_type=row.action_type,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        outcome=row.outcome,
        context=row.context if row.context is not None else {},
    )
