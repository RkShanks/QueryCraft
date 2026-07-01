"""RED unit test for retention window enforcement in AuditSearchService (T-878).

Contract under test:
  AuditSearchService.search() with no date filter must:
  1. Exclude entries older than retention_months (24) from results.
  2. Always include WHERE timestamp >= cutoff in the query — no query
     without the retention cutoff filter is allowed.

Approach:
  - Seed or mock entries spanning 25 months (some outside 24-month window).
  - Call AuditSearchService.search() with no date filter.
  - Assert entries older than retention_months are absent from results.
  - Assert query includes timestamp >= cutoff by capturing the SQL/ORM query.

FR/SC: FR-170, SC-069
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.audit_search import AuditSearchParams

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_entry(seq: int, offset_days: int):
    """Return a minimal entry-like object with timestamp offset_days in the past."""
    ts = datetime.now(UTC) - timedelta(days=offset_days)

    class _FakeEntry:
        sequence_number = seq
        action_type = "query.submit"
        actor_identity = "alice"
        outcome = "success"
        timestamp = ts
        resource_type = None
        resource_id = None
        context = {}

    return _FakeEntry()


def _build_mock_session_with_entries(entries):
    """Return an AsyncMock session whose execute() sides return count then rows."""
    session = AsyncMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = len(entries)

    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = entries

    session.execute = AsyncMock(side_effect=[count_result, rows_result])
    return session


def _assert_query_has_timestamp_cutoff(query):
    """Assert that the SQLAlchemy query has a filter matching 'timestamp >= cutoff'."""
    sql = str(query).lower()
    normalized = "".join(sql.split())
    assert "timestamp>=" in normalized, (
        f"SQL query is missing the timestamp lower-bound retention filter. Compiled SQL:\n{sql}"
    )


# ---------------------------------------------------------------------------
# T-878.1 — Entries older than retention window absent from results
# ---------------------------------------------------------------------------


class TestRetentionWindowExcludesOldEntries:
    """AuditSearchService must not return entries older than retention_months."""

    @pytest.mark.asyncio
    async def test_entries_older_than_24_months_absent(self):
        """Mock DB returns both recent and old entries; service excludes old ones.

        Strategy: Mock session to return a mix of entries. Then verify that
        _retention_cutoff is called and its result is included in the filter.
        This test verifies the service-layer contract: when _retention_cutoff
        is called with retention_months=24, any entry older than that cutoff
        is filtered out (we verify by patching _retention_cutoff to a recent
        date and confirming only entries that would pass the filter are returned).
        """
        from app.services.audit_search_service import AuditSearchService

        # 25-month span: some entries within 24 months, one beyond
        recent_entry = _make_fake_entry(seq=1, offset_days=10)  # 10 days ago → IN window
        _old_entry = _make_fake_entry(seq=2, offset_days=760)  # ~25 months ago → OUTSIDE window

        # Simulate the DB correctly filtering via WHERE: the mock only returns
        # recent_entry because the DB WHERE clause excluded old_entry.
        session = _build_mock_session_with_entries([recent_entry])

        params = AuditSearchParams()  # no date filter
        result = await AuditSearchService.search(session, params, retention_months=24)

        # Only recent entry present — old_entry was filtered by retention WHERE
        assert result.pagination.total_entries == 1
        assert len(result.entries) == 1
        assert result.entries[0].sequence_number == 1

        # Check call arguments
        assert session.execute.call_count == 2
        count_query = session.execute.call_args_list[0][0][0]
        data_query = session.execute.call_args_list[1][0][0]
        _assert_query_has_timestamp_cutoff(count_query)
        _assert_query_has_timestamp_cutoff(data_query)

    @pytest.mark.asyncio
    async def test_no_entries_returned_when_all_outside_window(self):
        """If all DB entries are outside the retention window, result is empty."""
        from app.services.audit_search_service import AuditSearchService

        # DB correctly returns nothing because all entries are filtered by WHERE
        session = _build_mock_session_with_entries([])
        # Override total count to 0 as well (both execute calls already return 0/[])
        session.execute = AsyncMock(
            side_effect=[
                _count_mock(0),
                _rows_mock([]),
            ]
        )

        params = AuditSearchParams()
        result = await AuditSearchService.search(session, params, retention_months=24)

        assert result.pagination.total_entries == 0
        assert result.entries == []

        # Check call arguments
        assert session.execute.call_count == 2
        count_query = session.execute.call_args_list[0][0][0]
        data_query = session.execute.call_args_list[1][0][0]
        _assert_query_has_timestamp_cutoff(count_query)
        _assert_query_has_timestamp_cutoff(data_query)


def _count_mock(n: int):
    m = MagicMock()
    m.scalar_one.return_value = n
    return m


def _rows_mock(entries):
    m = MagicMock()
    m.scalars.return_value.all.return_value = entries
    return m


# ---------------------------------------------------------------------------
# T-878.2 — Query includes WHERE timestamp >= cutoff (no unfiltered queries)
# ---------------------------------------------------------------------------


class TestRetentionWindowAppliedToQuery:
    """Every search query must include timestamp >= cutoff WHERE clause.

    Verification approach: capture the SQLAlchemy select() calls and assert
    the _retention_cutoff static method is invoked for every search call,
    confirming the cutoff is always applied.
    """

    @pytest.mark.asyncio
    async def test_retention_cutoff_called_for_every_search(self):
        """_retention_cutoff must be called exactly once per search() invocation."""
        from app.services.audit_search_service import AuditSearchService

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[_count_mock(0), _rows_mock([])])

        with patch.object(
            AuditSearchService, "_retention_cutoff", wraps=AuditSearchService._retention_cutoff
        ) as mock_cutoff:
            params = AuditSearchParams()
            await AuditSearchService.search(session, params, retention_months=24)
            mock_cutoff.assert_called_once_with(24)

    @pytest.mark.asyncio
    async def test_retention_cutoff_is_within_window(self):
        """_retention_cutoff(24) must return a datetime approximately 24 months ago.

        The cutoff should be at least 23 months in the past and at most 25 months
        in the past (fuzzy check tolerates relativedelta vs timedelta fallback).
        """
        from app.services.audit_search_service import AuditSearchService

        cutoff = AuditSearchService._retention_cutoff(24)
        now = datetime.now(UTC)

        # Must be in the past
        assert cutoff < now

        # Fuzzy bounds: 23 months (≈690 days) to 25 months (≈765 days) ago
        lower_bound = now - timedelta(days=765)  # 25 months
        upper_bound = now - timedelta(days=690)  # 23 months

        assert lower_bound <= cutoff <= upper_bound, (
            f"cutoff={cutoff!r} not in expected 23–25 month range [{lower_bound!r}, {upper_bound!r}]"
        )

    @pytest.mark.asyncio
    async def test_both_count_and_data_queries_execute(self):
        """search() must execute exactly 2 queries: COUNT then data SELECT.

        This verifies the retention cutoff is applied to both queries, not
        just one.
        """
        from app.services.audit_search_service import AuditSearchService

        executed_queries = []

        async def _capture(query, *args, **kwargs):
            executed_queries.append(query)
            if len(executed_queries) == 1:
                return _count_mock(0)
            return _rows_mock([])

        session = AsyncMock()
        session.execute = _capture

        params = AuditSearchParams()
        await AuditSearchService.search(session, params, retention_months=24)

        # Exactly two queries issued: COUNT(*) and data SELECT
        assert len(executed_queries) == 2
        _assert_query_has_timestamp_cutoff(executed_queries[0])
        _assert_query_has_timestamp_cutoff(executed_queries[1])

    @pytest.mark.asyncio
    async def test_search_without_date_filter_still_applies_retention(self):
        """No explicit start_date/end_date → retention cutoff still enforced.

        Regression guard: a naive implementation might skip the retention
        WHERE clause when no date params are provided.
        """
        from app.services.audit_search_service import AuditSearchService

        executed_queries = []

        async def _capture(query, *args, **kwargs):
            executed_queries.append(query)
            if len(executed_queries) == 1:
                return _count_mock(5)
            return _rows_mock([_make_fake_entry(seq=i, offset_days=i * 10) for i in range(1, 6)])

        session = AsyncMock()
        session.execute = _capture

        # No date filter at all — retention must still be applied
        params = AuditSearchParams()
        assert params.start_date is None
        assert params.end_date is None

        with patch.object(
            AuditSearchService, "_retention_cutoff", wraps=AuditSearchService._retention_cutoff
        ) as mock_cutoff:
            await AuditSearchService.search(session, params, retention_months=24)
            # cutoff must have been computed even with no date filter
            mock_cutoff.assert_called_once_with(24)

        assert len(executed_queries) == 2
        _assert_query_has_timestamp_cutoff(executed_queries[0])
        _assert_query_has_timestamp_cutoff(executed_queries[1])


# ---------------------------------------------------------------------------
# T-878.3 — 25-month span, retention=24: entries at boundary
# ---------------------------------------------------------------------------


class TestRetentionWindowBoundary:
    """Boundary behaviour: entry at exactly retention limit."""

    @pytest.mark.asyncio
    async def test_entry_at_exactly_24_months_included(self):
        """Entry at the boundary (24 months ago) should be included.

        The WHERE clause is timestamp >= cutoff (inclusive), so an entry
        at exactly the cutoff should be returned.
        """
        from app.services.audit_search_service import AuditSearchService

        boundary_entry = _make_fake_entry(seq=99, offset_days=730)  # ~24 months

        # Mock session: both count and rows return this entry
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[_count_mock(1), _rows_mock([boundary_entry])])

        params = AuditSearchParams()
        result = await AuditSearchService.search(session, params, retention_months=24)

        # The DB returned it (simulating the >= boundary — the entry is at limit)
        assert result.pagination.total_entries == 1
        assert result.entries[0].sequence_number == 99

        # Check call arguments
        assert session.execute.call_count == 2
        count_query = session.execute.call_args_list[0][0][0]
        data_query = session.execute.call_args_list[1][0][0]
        _assert_query_has_timestamp_cutoff(count_query)
        _assert_query_has_timestamp_cutoff(data_query)

    @pytest.mark.asyncio
    async def test_entries_spanning_25_months_with_24_month_window(self):
        """25-month span: entries within 24 months present, older absent.

        Seeds 25 monthly entries (entry_N is N*30 days old).
        With retention_months=24, entries 0..23 (within 24 months) are
        included and entry_24 (25 months = ~750 days) is excluded.

        Verified via mock: DB correctly applies the WHERE clause and only
        returns entries within the window.
        """
        from app.services.audit_search_service import AuditSearchService

        # 25 entries: 0 months old → 24 months old (all within window, by mock design)
        within_window = [_make_fake_entry(seq=i, offset_days=i * 30) for i in range(24)]
        # 1 entry: 25 months old (outside window — filtered by DB WHERE)
        # DB mock correctly excludes it

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[_count_mock(24), _rows_mock(within_window)])

        params = AuditSearchParams()
        result = await AuditSearchService.search(session, params, retention_months=24)

        assert result.pagination.total_entries == 24
        assert len(result.entries) == 24
        # Confirm no entry older than ~24 months (720 days) would appear
        for entry in result.entries:
            assert entry.sequence_number in range(24)

        # Check call arguments
        assert session.execute.call_count == 2
        count_query = session.execute.call_args_list[0][0][0]
        data_query = session.execute.call_args_list[1][0][0]
        _assert_query_has_timestamp_cutoff(count_query)
        _assert_query_has_timestamp_cutoff(data_query)
