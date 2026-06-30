"""RED unit tests for verify_chain() purge-gap handling (T-871).

Contract tested:
- verify_chain() on a log with a purge gap + valid audit.purge marker
  returns verified=True (gap treated as intentional).
- verify_chain() on a log with a gap and NO matching marker returns
  verified=False (gap treated as tampering).
- verify_chain() matches the marker's first_surviving_prev_hash to the
  orphaned prev_hash of the first surviving entry.
- Normal chain without purge still verifies correctly.

These tests require a real DB session because verify_chain() issues
SELECT queries against the audit_log_entries table.  The pattern mirrors
test_audit_chain_verification.py and test_purge_gap_marker.py.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType
from app.services.audit_service import AuditService, _compute_row_hash

# ---------------------------------------------------------------------------
# Helpers — direct DB seeding with correct chained hashes
# ---------------------------------------------------------------------------


def _payload_for(
    seq: int,
    ts: datetime,
    action: str = "query.submit",
    context: dict | None = None,
) -> dict[str, Any]:
    return {
        "sequence_number": seq,
        "timestamp": ts.isoformat(),
        "actor_id": None,
        "actor_identity": None,
        "action_type": action,
        "resource_type": None,
        "resource_id": None,
        "outcome": "success",
        "context": context or {},
    }


async def _seed_entry(
    db_session,
    sequence_number: int,
    timestamp: datetime,
    prev_hash: str,
    action: str = "query.submit",
    context: dict | None = None,
) -> AuditLogEntry:
    """Insert a minimal AuditLogEntry with correct chained hashes."""
    payload = _payload_for(sequence_number, timestamp, action, context)
    row_hash = _compute_row_hash(payload, prev_hash)
    entry = AuditLogEntry(
        sequence_number=sequence_number,
        timestamp=timestamp,
        action_type=action,
        outcome="success",
        prev_hash=prev_hash,
        row_hash=row_hash,
        context=context or {},
    )
    db_session.add(entry)
    await db_session.flush()
    return entry


async def _seed_chain(db_session, timestamps: list[datetime]) -> list[AuditLogEntry]:
    """Seed a proper chained sequence starting at seq=1."""
    entries: list[AuditLogEntry] = []
    prev_hash = "GENESIS"
    for i, ts in enumerate(timestamps, start=1):
        entry = await _seed_entry(db_session, i, ts, prev_hash)
        prev_hash = entry.row_hash
        entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# T-871.1 — Normal chain without purge verifies correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestVerifyChainNormalCase:
    """verify_chain() must still verify an intact chain with no purge."""

    async def test_intact_chain_no_purge_verifies_true(self, db_session):
        """Intact chain of 3 entries with no gaps must verify as True."""
        now = datetime.now(UTC)
        await _seed_chain(
            db_session,
            [
                now - timedelta(days=3),
                now - timedelta(days=2),
                now - timedelta(days=1),
            ],
        )

        result = await AuditService.verify_chain(db_session)

        assert result.verified is True
        assert result.first_break_at is None
        assert result.entries_checked == 3

    async def test_empty_chain_verifies_true(self, db_session):
        """Empty audit log has nothing to break — must verify as True."""
        result = await AuditService.verify_chain(db_session)

        assert result.verified is True
        assert result.first_break_at is None
        assert result.entries_checked == 0

    async def test_single_entry_chain_verifies_true(self, db_session):
        """Single genesis entry must verify as True."""
        now = datetime.now(UTC)
        await _seed_chain(db_session, [now - timedelta(days=1)])

        result = await AuditService.verify_chain(db_session)

        assert result.verified is True
        assert result.first_break_at is None


# ---------------------------------------------------------------------------
# T-871.2 — Purge gap with valid marker → verified=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestVerifyChainWithValidPurgeMarker:
    """verify_chain() must treat a gap backed by a matching audit.purge marker
    as intentional and return verified=True."""

    async def test_purge_gap_with_valid_marker_returns_verified_true(self, db_session):
        """Simulate a realistic purge: seed entries, call purge, then verify.

        The retained chain after purge will be:
          [surviving entry (seq=2), purge marker (seq=3)]

        The surviving entry's prev_hash points to the deleted seq=1, but
        the purge marker records first_surviving_prev_hash so verify_chain
        can reconcile the gap.
        """
        now = datetime.now(UTC)
        old = now - timedelta(days=400)  # will be purged (seq=1)
        recent = now - timedelta(days=5)  # will survive (seq=2)

        await _seed_chain(db_session, [old, recent])

        # Perform the purge — inserts audit.purge marker at seq=3
        deleted = await AuditService.purge_expired_entries(db_session, retention_months=6)
        assert deleted == 1, "Expected 1 expired entry to be deleted"

        # verify_chain must return True: purge gap is backed by the marker
        result = await AuditService.verify_chain(db_session)

        assert result.verified is True, (
            f"verify_chain must return verified=True when a valid purge marker covers the gap; "
            f"got verified={result.verified!r}, first_break_at={result.first_break_at!r}"
        )
        assert result.first_break_at is None

    async def test_multiple_purged_entries_gap_with_valid_marker_verifies(self, db_session):
        """Multiple old entries purged; single surviving entry + marker must verify."""
        now = datetime.now(UTC)
        old1 = now - timedelta(days=500)
        old2 = now - timedelta(days=450)
        old3 = now - timedelta(days=400)
        recent = now - timedelta(days=5)

        await _seed_chain(db_session, [old1, old2, old3, recent])

        deleted = await AuditService.purge_expired_entries(db_session, retention_months=6)
        assert deleted == 3

        result = await AuditService.verify_chain(db_session)

        assert result.verified is True, (
            f"verify_chain must return True for multi-entry gap with valid marker; "
            f"first_break_at={result.first_break_at!r}"
        )
        assert result.first_break_at is None

    async def test_entries_appended_after_purge_still_verify(self, db_session):
        """Chain continues to grow after purge; full retained chain must verify."""
        now = datetime.now(UTC)
        old = now - timedelta(days=400)
        recent = now - timedelta(days=5)

        await _seed_chain(db_session, [old, recent])

        # Purge inserts marker at seq=3
        await AuditService.purge_expired_entries(db_session, retention_months=6)

        # New entry appended after purge (seq=4)
        await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)

        result = await AuditService.verify_chain(db_session)

        assert result.verified is True, (
            f"Chain with purge gap + subsequent entries must verify; first_break_at={result.first_break_at!r}"
        )
        assert result.first_break_at is None


# ---------------------------------------------------------------------------
# T-871.3 — Purge marker matching: first_surviving_prev_hash linkage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestVerifyChainMarkerMatching:
    """verify_chain() must use first_surviving_prev_hash from the purge marker
    to reconcile the orphaned prev_hash of the first surviving entry."""

    async def test_marker_first_surviving_prev_hash_matches_orphaned_prev_hash(self, db_session):
        """The first surviving entry's prev_hash must match the marker's
        first_surviving_prev_hash, enabling verify_chain to bridge the gap."""
        from sqlalchemy import select

        now = datetime.now(UTC)
        old = now - timedelta(days=400)
        recent = now - timedelta(days=5)

        seeded = await _seed_chain(db_session, [old, recent])
        # seeded[1].prev_hash = seeded[0].row_hash  (the deleted entry's hash)
        orphaned_prev_hash = seeded[1].prev_hash

        await AuditService.purge_expired_entries(db_session, retention_months=6)

        # Confirm the marker stores the orphaned prev_hash as first_surviving_prev_hash
        result = await db_session.execute(
            select(AuditLogEntry).where(AuditLogEntry.action_type == AuditActionType.AUDIT_PURGE.value)
        )
        marker = result.scalar_one()
        assert marker.context["first_surviving_prev_hash"] == orphaned_prev_hash, (
            "Marker must record the orphaned prev_hash as first_surviving_prev_hash"
        )

        # Now verify the full chain
        verify_result = await AuditService.verify_chain(db_session)
        assert verify_result.verified is True, (
            "verify_chain must bridge the gap using the marker's first_surviving_prev_hash"
        )

    async def test_verify_chain_counts_surviving_entries_and_marker(self, db_session):
        """entries_checked must include the surviving entry AND the purge marker."""
        now = datetime.now(UTC)
        old = now - timedelta(days=400)
        recent = now - timedelta(days=5)

        await _seed_chain(db_session, [old, recent])
        await AuditService.purge_expired_entries(db_session, retention_months=6)

        result = await AuditService.verify_chain(db_session)

        # 1 deleted (seq=1), 1 surviving (seq=2), 1 marker (seq=3) = 2 checked
        assert result.entries_checked == 2, (
            f"entries_checked must be 2 (survivor + marker); got {result.entries_checked}"
        )


# ---------------------------------------------------------------------------
# T-871.4 — Gap with NO matching purge marker → verified=False (tampering)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestVerifyChainGapWithoutMarker:
    """verify_chain() must report verified=False when an orphaned prev_hash
    is not backed by any matching audit.purge marker — this indicates tampering."""

    async def _build_gap_without_marker(self, db_session) -> tuple[int, str]:
        """Seed a chain with a deliberate gap but NO purge marker.

        Creates: seq=1 (genesis entry)  then seq=3 with orphaned prev_hash.
        There is no seq=2 and no purge marker — simulates deletion without
        a proper purge marker.

        Returns (orphaned_seq, orphaned_prev_hash).
        """
        now = datetime.now(UTC)

        # seq=1
        await _seed_entry(db_session, 1, now - timedelta(days=10), "GENESIS")

        # seq=3 directly, with orphaned prev_hash (pointing at the hash of a
        # deleted seq=2 that never existed in the DB).
        fake_deleted_hash = "a" * 64  # hash of a "deleted" seq=2 that was never stored
        orphaned_entry = await _seed_entry(db_session, 3, now - timedelta(days=1), fake_deleted_hash)
        return orphaned_entry.sequence_number, fake_deleted_hash

    async def test_gap_without_marker_returns_verified_false(self, db_session):
        """Gap in sequence with no matching purge marker must be reported as tampering."""
        orphaned_seq, _ = await self._build_gap_without_marker(db_session)

        result = await AuditService.verify_chain(db_session)

        assert result.verified is False, (
            "verify_chain must return verified=False for a gap with no matching purge marker"
        )
        assert result.first_break_at is not None, "first_break_at must be set when tampering is detected"

    async def test_gap_without_marker_first_break_at_is_orphaned_entry(self, db_session):
        """first_break_at must point to the first entry with an orphaned prev_hash."""
        orphaned_seq, _ = await self._build_gap_without_marker(db_session)

        result = await AuditService.verify_chain(db_session)

        assert result.first_break_at == orphaned_seq, (
            f"first_break_at must be {orphaned_seq} (the orphaned entry); got {result.first_break_at!r}"
        )

    async def test_mismatched_marker_context_treated_as_tampering(self, db_session):
        """A purge marker with WRONG first_surviving_prev_hash must NOT cover the gap.

        Inserts a fake purge marker with a first_surviving_prev_hash that does
        NOT match the orphaned entry's prev_hash, so verify_chain must still
        report tampering.
        """
        now = datetime.now(UTC)

        # seq=1: genesis entry
        entry1 = await _seed_entry(db_session, 1, now - timedelta(days=10), "GENESIS")

        # seq=2: a fake "purge marker" with WRONG first_surviving_prev_hash
        wrong_hash = "b" * 64
        correct_orphaned_hash = "c" * 64  # different from what seq=3 will reference

        fake_marker_context = {
            "purged_from_seq": 99,
            "purged_to_seq": 99,
            "purged_count": 1,
            "retention_months": 6,
            "first_surviving_seq": 3,
            "first_surviving_prev_hash": wrong_hash,  # WRONG — won't match seq=3's prev_hash
            "last_retained_hash": "d" * 64,
            "last_retained_seq": 99,
        }
        fake_marker = await _seed_entry(
            db_session,
            2,
            now - timedelta(days=5),
            entry1.row_hash,
            action=AuditActionType.AUDIT_PURGE.value,
            context=fake_marker_context,
        )

        # seq=3: orphaned entry whose prev_hash does NOT match the marker
        await _seed_entry(db_session, 3, now - timedelta(days=1), correct_orphaned_hash)
        _ = fake_marker  # marker is in DB; variable referenced to avoid F841

        result = await AuditService.verify_chain(db_session)

        assert result.verified is False, "Mismatched purge marker must not cover the gap — must report tampering"
