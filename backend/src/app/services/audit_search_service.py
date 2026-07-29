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
from calendar import monthrange
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log_entry import AuditLogEntry
from app.schemas.audit_search import AuditEntryRead, AuditSearchPagination, AuditSearchParams, AuditSearchResponse
from app.services.audit_redaction import redact_audit_entry


class AuditSearchService:
    """Filtered + paginated audit log search with server-side retention enforcement."""

    @staticmethod
    def _retention_cutoff(retention_months: int, *, now: datetime | None = None) -> datetime:
        """Compute an inclusive calendar-month cutoff in UTC."""
        current = now or datetime.now(UTC)
        current = current.replace(tzinfo=UTC) if current.tzinfo is None else current.astimezone(UTC)

        target_month_index = current.year * 12 + current.month - 1 - retention_months
        target_year, zero_based_month = divmod(target_month_index, 12)
        target_month = zero_based_month + 1
        target_day = min(current.day, monthrange(target_year, target_month)[1])
        return current.replace(year=target_year, month=target_month, day=target_day)

    @staticmethod
    def _build_filters(params: AuditSearchParams, cutoff: datetime) -> list[Any]:
        """Construct common SQLAlchemy filters."""
        filters = [AuditLogEntry.timestamp >= cutoff]
        if params.action_type is not None:
            filters.append(AuditLogEntry.action_type == params.action_type)
        if params.actor_identity is not None:
            filters.append(AuditLogEntry.actor_identity == params.actor_identity)
        if params.outcome is not None:
            filters.append(AuditLogEntry.outcome == params.outcome)
        if params.resource_type is not None:
            filters.append(AuditLogEntry.resource_type == params.resource_type)
        if params.start_date is not None:
            filters.append(AuditLogEntry.timestamp >= params.start_date)
        if params.end_date is not None:
            filters.append(AuditLogEntry.timestamp <= params.end_date)
        return filters

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
        base_filters = cls._build_filters(params, cutoff)

        # Count and snapshot the upper sequence boundary atomically. Appends
        # committed after this statement are excluded from both the page and
        # its metadata, so one request cannot chase a moving result set.
        snapshot_query = (
            select(func.count(), func.max(AuditLogEntry.sequence_number))
            .select_from(AuditLogEntry)
            .where(*base_filters)
        )
        snapshot_result = await session.execute(snapshot_query)
        total_entries_raw, upper_sequence = snapshot_result.one()
        total_entries = int(total_entries_raw)

        # Offset pagination is deterministic for this request snapshot. Each
        # page request takes a fresh snapshot; callers traversing pages while
        # inserts occur can therefore observe ordinary offset-pagination
        # drift across requests and should restart traversal when exact
        # point-in-time pagination is required.
        offset = (params.page - 1) * params.page_size
        data_filters = list(base_filters)
        if upper_sequence is not None:
            data_filters.append(AuditLogEntry.sequence_number <= int(upper_sequence))
        data_query = (
            select(AuditLogEntry)
            .where(*data_filters)
            .order_by(AuditLogEntry.timestamp.desc(), AuditLogEntry.sequence_number.desc())
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

    @classmethod
    async def get_all_entries_for_export(
        cls,
        session: AsyncSession,
        retention_months: int,
        export_limit: int = 50_000,
        *,
        action_type: str | None = None,
        actor_identity: str | None = None,
        outcome: str | None = None,
        resource_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[int, list[AuditEntryRead]]:
        """Fetch all matching entries for export without the page-size schema cap.

        Uses the same retention cutoff and ORM filter logic as ``search()`` but
        issues a single uncapped SELECT (bounded by ``export_limit``) rather than
        going through ``AuditSearchParams`` which has ``page_size le=100``.

        Parameters
        ----------
        session:
            Async SQLAlchemy session.
        retention_months:
            Entries older than this many months are excluded before any other
            filter. Uses relativedelta when available, falls back to 30d/month.
        export_limit:
            Hard upper bound on rows fetched (default 50,000). Caller should
            check ``total_count > export_limit`` BEFORE calling this method and
            reject the request early, but the LIMIT clause is a safety net.
        action_type, actor_identity, outcome, resource_type,
        start_date, end_date:
            Optional caller filters. ``None`` means no constraint on that field.

        Returns
        -------
        tuple[int, list[AuditEntryRead]]
            ``(total_count, entries)`` where ``total_count`` is the true
            COUNT(*) and ``entries`` is the fetched list ordered by
            ``timestamp DESC``.
        """
        # Reuse _retention_cutoff (relativedelta-aware) + _build_filters,
        # but pass a minimal AuditSearchParams with only the filter fields —
        # page/page_size are never referenced by _build_filters.
        cutoff = cls._retention_cutoff(retention_months)
        # Build filters using a minimal param object (page_size default=50 is irrelevant
        # here since _build_filters never reads it).
        from app.schemas.audit_search import AuditSearchParams as _ASP

        _params = _ASP(
            action_type=action_type,
            actor_identity=actor_identity,
            outcome=outcome,
            resource_type=resource_type,
            start_date=start_date,
            end_date=end_date,
            # page / page_size use defaults (1 / 50) — _build_filters ignores them.
        )
        base_filters = cls._build_filters(_params, cutoff)

        # Count and snapshot in one statement. This keeps the 50k guard and
        # exported rows internally consistent when appends occur concurrently.
        snapshot_query = (
            select(func.count(), func.max(AuditLogEntry.sequence_number))
            .select_from(AuditLogEntry)
            .where(*base_filters)
        )
        snapshot_result = await session.execute(snapshot_query)
        total_count_raw, upper_sequence = snapshot_result.one()
        total_count = int(total_count_raw)

        data_filters = list(base_filters)
        if upper_sequence is not None:
            data_filters.append(AuditLogEntry.sequence_number <= int(upper_sequence))

        # LIMIT is the hard export ceiling, not a Pydantic page_size.
        data_query = (
            select(AuditLogEntry)
            .where(*data_filters)
            .order_by(AuditLogEntry.timestamp.desc(), AuditLogEntry.sequence_number.desc())
            .limit(export_limit)
        )
        rows_result = await session.execute(data_query)
        entries = [_row_to_read(row) for row in rows_result.scalars().all()]
        return total_count, entries


def _row_to_read(row: Any) -> AuditEntryRead:
    """Convert an ORM row to a defense-in-depth redacted response."""
    redacted = redact_audit_entry(row)
    return AuditEntryRead(
        sequence_number=row.sequence_number,
        timestamp=row.timestamp,
        actor_identity=redacted["actor_identity"],
        action_type=redacted["action_type"],
        resource_type=redacted["resource_type"],
        resource_id=redacted["resource_id"],
        outcome=redacted["outcome"],
        context=redacted["context"],
    )
