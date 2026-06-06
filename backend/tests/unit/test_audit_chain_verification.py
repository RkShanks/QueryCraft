"""Tests for audit chain verification (T-621)."""

from datetime import UTC, datetime

import pytest

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType
from app.services.audit_service import AuditService


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestAuditChainVerification:
    """Chain integrity: intact, broken, first break reporting.

    Tests that manually insert tampered entries at fixed
    sequence numbers (1 or 2) assume a clean audit table;
    the ``clean_audit_table`` fixture truncates the shared
    test container's audit table before each test runs.
    """

    async def test_intact_chain_verifies_true(self, db_session):
        await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)
        await AuditService.log(db_session, action=AuditActionType.QUERY_EXECUTE)
        result = await AuditService.verify_chain(db_session)
        assert result.verified is True
        assert result.entries_checked >= 2
        assert result.first_break_at is None

    async def test_broken_chain_detects_first_break(self, db_session):
        # Insert one valid entry
        await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)

        # Insert tampered entry at sequence 2
        bad = AuditLogEntry(
            sequence_number=2,
            timestamp=datetime.now(UTC),
            action_type="query.execute",
            outcome="success",
            prev_hash="GENESIS",
            row_hash="0" * 64,
            context={},
        )
        db_session.add(bad)
        await db_session.flush()

        result = await AuditService.verify_chain(db_session)
        assert result.verified is False
        assert result.first_break_at == 2

    async def test_chain_continues_after_break(self, db_session):
        # Tampered entry at sequence 1
        bad = AuditLogEntry(
            sequence_number=1,
            timestamp=datetime.now(UTC),
            action_type="query.execute",
            outcome="success",
            prev_hash="GENESIS",
            row_hash="deadbeef" * 8,
            context={},
        )
        db_session.add(bad)
        await db_session.flush()

        # New valid entry after break
        e2 = await AuditService.log(db_session, action=AuditActionType.QUERY_ACCEPT)
        result = await AuditService.verify_chain(db_session)
        # Break at 1; chain continues without auto-repair
        assert result.first_break_at == 1
        # Make sure second entry exists (appending continues)
        assert e2.sequence_number == 2
