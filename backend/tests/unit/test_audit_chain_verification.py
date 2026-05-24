"""Tests for audit chain verification (T-621)."""

import hashlib
import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType
from app.services.audit_service import AuditService


def _compute_hash(payload: dict, prev_hash: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{canonical}{prev_hash}".encode()).hexdigest()


@pytest.mark.asyncio
class TestAuditChainVerification:
    """Chain integrity: intact, broken, first break reporting."""

    async def test_intact_chain_verifies_true(self, db_session):
        await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)
        await AuditService.log(db_session, action=AuditActionType.QUERY_EXECUTE)
        result = await AuditService.verify_chain(db_session)
        assert result.verified is True
        assert result.entries_checked >= 2
        assert result.first_break_at is None

    async def test_broken_chain_detects_first_break(self, db_session):
        # Insert two valid entries
        await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)
        await AuditService.log(db_session, action=AuditActionType.QUERY_EXECUTE)

        # Insert third with wrong hash (simulate tampering)
        bad = AuditLogEntry(
            sequence_number=3,
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
        assert result.first_break_at == 3

    async def test_genesis_entry_prev_hash(self, db_session):
        await AuditService.log(db_session, action=AuditActionType.AUDIT_VERIFY)
        result = await db_session.execute(select(AuditLogEntry).order_by(AuditLogEntry.sequence_number))
        entry = result.scalars().first()
        assert entry.prev_hash == "GENESIS"

    async def test_chain_continues_after_break(self, db_session):
        # Tampered entry
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
        e3 = await AuditService.log(db_session, action=AuditActionType.QUERY_ACCEPT)
        result = await AuditService.verify_chain(db_session)
        # Break at 1; chain continues without auto-repair
        assert result.first_break_at == 1
        # Make sure second entry exists (appending continues)
        assert e3.sequence_number == 2
