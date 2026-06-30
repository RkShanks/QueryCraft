"""RED unit tests for purge-gap marker (T-869).

Contract tested:
- AuditService.purge_expired_entries() inserts an audit.purge marker
  BEFORE deleting expired entries, in the same transaction.
- Marker context contains all required fields:
    purged_from_seq, purged_to_seq, purged_count,
    retention_months, first_surviving_seq, first_surviving_prev_hash,
    last_retained_hash, last_retained_seq.
- No existing audit entries are modified (immutability preserved).
- The marker is itself immutable (before_delete/before_update guards apply).

These tests are integration-style (require DB) because the marker
creation is part of a real database transaction. They mirror the
test approach in test_audit_retention.py.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType
from app.services.audit_service import AuditService, _compute_row_hash

# ---------------------------------------------------------------------------
# Helpers — reuse the same seeding pattern from test_audit_retention.py
# ---------------------------------------------------------------------------


def _payload_for(seq: int, ts: datetime, action: str = "query.submit") -> dict[str, Any]:
    return {
        "sequence_number": seq,
        "timestamp": ts.isoformat(),
        "actor_id": None,
        "actor_identity": None,
        "action_type": action,
        "resource_type": None,
        "resource_id": None,
        "outcome": "success",
        "context": {},
    }


async def _seed_entry(
    db_session,
    sequence_number: int,
    timestamp: datetime,
    prev_hash: str,
    action: str = "query.submit",
) -> AuditLogEntry:
    """Insert a minimal AuditLogEntry with correct chained hashes."""
    payload = _payload_for(sequence_number, timestamp, action)
    row_hash = _compute_row_hash(payload, prev_hash)
    entry = AuditLogEntry(
        sequence_number=sequence_number,
        timestamp=timestamp,
        action_type=action,
        outcome="success",
        prev_hash=prev_hash,
        row_hash=row_hash,
        context={},
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
# T-869.1 — Marker inserted BEFORE deletion in same transaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestPurgeMarkerInsertedBeforeDeletion:
    """purge_expired_entries() inserts audit.purge marker before deleting."""

    async def test_purge_inserts_marker_entry(self, db_session):
        """After purge, a marker with action_type=audit.purge must exist."""
        from sqlalchemy import select

        now = datetime.now(UTC)
        old = now - timedelta(days=400)  # will be purged
        recent = now - timedelta(days=5)  # will survive

        await _seed_chain(db_session, [old, recent])

        await AuditService.purge_expired_entries(db_session, retention_months=6)

        result = await db_session.execute(
            select(AuditLogEntry).where(AuditLogEntry.action_type == AuditActionType.AUDIT_PURGE.value)
        )
        marker = result.scalar_one_or_none()
        assert marker is not None, "Expected audit.purge marker to be inserted"

    async def test_purge_marker_is_latest_entry(self, db_session):
        """Marker must have a higher sequence_number than all surviving entries."""
        from sqlalchemy import select

        now = datetime.now(UTC)
        old = now - timedelta(days=400)
        recent = now - timedelta(days=5)

        await _seed_chain(db_session, [old, recent])

        await AuditService.purge_expired_entries(db_session, retention_months=6)

        result = await db_session.execute(select(AuditLogEntry).order_by(AuditLogEntry.sequence_number.asc()))
        surviving = result.scalars().all()
        # All remaining entries; marker must be the last
        assert surviving, "Expected at least one entry after purge"
        last_entry = surviving[-1]
        assert last_entry.action_type == AuditActionType.AUDIT_PURGE.value, (
            f"Last entry must be the purge marker, got action_type={last_entry.action_type!r}"
        )

    async def test_no_purge_marker_when_nothing_to_purge(self, db_session):
        """When no entries are expired, no purge marker should be inserted."""
        from sqlalchemy import select

        now = datetime.now(UTC)
        recent = now - timedelta(days=5)

        await _seed_chain(db_session, [recent])

        await AuditService.purge_expired_entries(db_session, retention_months=24)

        result = await db_session.execute(
            select(AuditLogEntry).where(AuditLogEntry.action_type == AuditActionType.AUDIT_PURGE.value)
        )
        marker = result.scalar_one_or_none()
        assert marker is None, "No purge marker should be inserted when nothing is purged"


# ---------------------------------------------------------------------------
# T-869.2 — Marker context contains all required fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestPurgeMarkerContextFields:
    """Marker context must contain all required boundary metadata fields."""

    REQUIRED_CONTEXT_KEYS = {
        "purged_from_seq",
        "purged_to_seq",
        "purged_count",
        "retention_months",
        "first_surviving_seq",
        "first_surviving_prev_hash",
        "last_retained_hash",
        "last_retained_seq",
    }

    async def _get_purge_marker(self, db_session):
        from sqlalchemy import select

        result = await db_session.execute(
            select(AuditLogEntry).where(AuditLogEntry.action_type == AuditActionType.AUDIT_PURGE.value)
        )
        return result.scalar_one()

    async def test_all_required_context_keys_present(self, db_session):
        """Marker context must contain all 8 required fields."""
        now = datetime.now(UTC)
        old1 = now - timedelta(days=400)
        old2 = now - timedelta(days=380)
        recent = now - timedelta(days=5)

        await _seed_chain(db_session, [old1, old2, recent])

        await AuditService.purge_expired_entries(db_session, retention_months=6)

        marker = await self._get_purge_marker(db_session)
        missing = self.REQUIRED_CONTEXT_KEYS - set(marker.context.keys())
        assert not missing, f"Marker context missing required keys: {missing}"

    async def test_purged_from_seq_is_min_purged(self, db_session):
        """purged_from_seq must be the sequence_number of the first purged entry."""
        now = datetime.now(UTC)
        old1 = now - timedelta(days=400)
        old2 = now - timedelta(days=380)
        recent = now - timedelta(days=5)

        seeded = await _seed_chain(db_session, [old1, old2, recent])
        # seq=1, seq=2 will be purged; seq=3 survives

        await AuditService.purge_expired_entries(db_session, retention_months=6)

        marker = await self._get_purge_marker(db_session)
        assert marker.context["purged_from_seq"] == seeded[0].sequence_number, (
            f"purged_from_seq should be {seeded[0].sequence_number}, got {marker.context['purged_from_seq']}"
        )

    async def test_purged_to_seq_is_max_purged(self, db_session):
        """purged_to_seq must be the sequence_number of the last purged entry."""
        now = datetime.now(UTC)
        old1 = now - timedelta(days=400)
        old2 = now - timedelta(days=380)
        recent = now - timedelta(days=5)

        seeded = await _seed_chain(db_session, [old1, old2, recent])

        await AuditService.purge_expired_entries(db_session, retention_months=6)

        marker = await self._get_purge_marker(db_session)
        assert marker.context["purged_to_seq"] == seeded[1].sequence_number, (
            f"purged_to_seq should be {seeded[1].sequence_number}, got {marker.context['purged_to_seq']}"
        )

    async def test_purged_count_matches_deleted(self, db_session):
        """purged_count must equal the number of deleted entries."""
        now = datetime.now(UTC)
        old1 = now - timedelta(days=400)
        old2 = now - timedelta(days=380)
        recent = now - timedelta(days=5)

        await _seed_chain(db_session, [old1, old2, recent])

        deleted = await AuditService.purge_expired_entries(db_session, retention_months=6)

        marker = await self._get_purge_marker(db_session)
        assert marker.context["purged_count"] == deleted == 2

    async def test_retention_months_in_context(self, db_session):
        """retention_months in context must match the value used for purge."""
        now = datetime.now(UTC)
        old = now - timedelta(days=400)
        recent = now - timedelta(days=5)

        await _seed_chain(db_session, [old, recent])

        await AuditService.purge_expired_entries(db_session, retention_months=9)

        marker = await self._get_purge_marker(db_session)
        assert marker.context["retention_months"] == 9

    async def test_first_surviving_seq_is_correct(self, db_session):
        """first_surviving_seq must be the sequence of the first retained entry."""
        now = datetime.now(UTC)
        old1 = now - timedelta(days=400)
        old2 = now - timedelta(days=380)
        recent = now - timedelta(days=5)

        seeded = await _seed_chain(db_session, [old1, old2, recent])

        await AuditService.purge_expired_entries(db_session, retention_months=6)

        marker = await self._get_purge_marker(db_session)
        # seq=3 (recent) is the first survivor
        assert marker.context["first_surviving_seq"] == seeded[2].sequence_number

    async def test_first_surviving_prev_hash_is_correct(self, db_session):
        """first_surviving_prev_hash must match the first surviving entry's prev_hash."""
        now = datetime.now(UTC)
        old1 = now - timedelta(days=400)
        old2 = now - timedelta(days=380)
        recent = now - timedelta(days=5)

        seeded = await _seed_chain(db_session, [old1, old2, recent])

        # Capture the first survivor's prev_hash before purge
        first_survivor_prev_hash = seeded[2].prev_hash

        await AuditService.purge_expired_entries(db_session, retention_months=6)

        marker = await self._get_purge_marker(db_session)
        assert marker.context["first_surviving_prev_hash"] == first_survivor_prev_hash

    async def test_last_retained_hash_is_correct(self, db_session):
        """last_retained_hash must be the row_hash of the last purged entry."""
        now = datetime.now(UTC)
        old1 = now - timedelta(days=400)
        old2 = now - timedelta(days=380)
        recent = now - timedelta(days=5)

        seeded = await _seed_chain(db_session, [old1, old2, recent])

        # The last purged entry is seq=2
        last_purged_hash = seeded[1].row_hash

        await AuditService.purge_expired_entries(db_session, retention_months=6)

        marker = await self._get_purge_marker(db_session)
        assert marker.context["last_retained_hash"] == last_purged_hash

    async def test_last_retained_seq_is_correct(self, db_session):
        """last_retained_seq must be the sequence_number of the last purged entry."""
        now = datetime.now(UTC)
        old1 = now - timedelta(days=400)
        old2 = now - timedelta(days=380)
        recent = now - timedelta(days=5)

        seeded = await _seed_chain(db_session, [old1, old2, recent])

        await AuditService.purge_expired_entries(db_session, retention_months=6)

        marker = await self._get_purge_marker(db_session)
        # seq=2 is the last purged (last_retained = last one that was retained before surviving)
        assert marker.context["last_retained_seq"] == seeded[1].sequence_number


# ---------------------------------------------------------------------------
# T-869.3 — Existing entries are not modified (immutability preserved)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestPurgeDoesNotModifyExistingEntries:
    """Existing audit entries must not be modified by purge_expired_entries()."""

    async def test_surviving_entries_unchanged(self, db_session):
        """row_hash and prev_hash of surviving entries must be unchanged after purge."""
        from sqlalchemy import select

        now = datetime.now(UTC)
        old = now - timedelta(days=400)
        recent = now - timedelta(days=5)

        seeded = await _seed_chain(db_session, [old, recent])

        # Capture pre-purge hashes of the surviving entry
        survivor_seq = seeded[1].sequence_number
        survivor_prev_hash_before = seeded[1].prev_hash
        survivor_row_hash_before = seeded[1].row_hash

        await AuditService.purge_expired_entries(db_session, retention_months=6)

        # Refetch the surviving entry
        result = await db_session.execute(select(AuditLogEntry).where(AuditLogEntry.sequence_number == survivor_seq))
        survivor = result.scalar_one()
        assert survivor.prev_hash == survivor_prev_hash_before, (
            "prev_hash of surviving entry must not be modified by purge"
        )
        assert survivor.row_hash == survivor_row_hash_before, (
            "row_hash of surviving entry must not be modified by purge"
        )

    async def test_orm_delete_on_marker_raises(self, db_session):
        """The purge marker is itself immutable — ORM delete must raise RuntimeError."""
        from sqlalchemy import select

        now = datetime.now(UTC)
        old = now - timedelta(days=400)
        recent = now - timedelta(days=5)

        await _seed_chain(db_session, [old, recent])
        await AuditService.purge_expired_entries(db_session, retention_months=6)

        result = await db_session.execute(
            select(AuditLogEntry).where(AuditLogEntry.action_type == AuditActionType.AUDIT_PURGE.value)
        )
        marker = result.scalar_one()

        # Attempting ORM delete on the marker must raise the immutability guard
        await db_session.delete(marker)
        with pytest.raises(RuntimeError, match="immutable"):
            await db_session.flush()

    async def test_orm_update_on_marker_raises(self, db_session):
        """The purge marker is itself immutable — ORM update must raise RuntimeError."""
        from sqlalchemy import select

        now = datetime.now(UTC)
        old = now - timedelta(days=400)
        recent = now - timedelta(days=5)

        await _seed_chain(db_session, [old, recent])
        await AuditService.purge_expired_entries(db_session, retention_months=6)

        result = await db_session.execute(
            select(AuditLogEntry).where(AuditLogEntry.action_type == AuditActionType.AUDIT_PURGE.value)
        )
        marker = result.scalar_one()

        # Attempting ORM update on the marker must raise the immutability guard
        marker.outcome = "tampered"
        with pytest.raises(RuntimeError, match="immutable"):
            await db_session.flush()


# ---------------------------------------------------------------------------
# T-869.4 — Marker chains normally into hash sequence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestPurgeMarkerChainsIntoHashSequence:
    """Marker must have valid prev_hash linking it to the previous entry."""

    async def test_marker_prev_hash_links_to_preceding_entry(self, db_session):
        """Marker's prev_hash must equal the row_hash of the entry just before it."""
        from sqlalchemy import select

        now = datetime.now(UTC)
        old = now - timedelta(days=400)
        recent = now - timedelta(days=5)

        await _seed_chain(db_session, [old, recent])

        await AuditService.purge_expired_entries(db_session, retention_months=6)

        # After purge: seq=1 deleted, seq=2 survives, seq=3 is marker
        result = await db_session.execute(select(AuditLogEntry).order_by(AuditLogEntry.sequence_number.asc()))
        all_entries = result.scalars().all()
        assert len(all_entries) == 2, f"Expected 2 entries (survivor + marker), got {len(all_entries)}"

        survivor = all_entries[0]
        marker = all_entries[1]

        assert marker.action_type == AuditActionType.AUDIT_PURGE.value
        assert marker.prev_hash == survivor.row_hash, (
            f"Marker prev_hash {marker.prev_hash!r} must equal preceding entry row_hash {survivor.row_hash!r}"
        )

    async def test_marker_row_hash_is_valid(self, db_session):
        """Marker's row_hash must be the correct SHA-256 for its payload+prev_hash."""
        from sqlalchemy import select

        from app.services.audit_service import _compute_row_hash

        now = datetime.now(UTC)
        old = now - timedelta(days=400)
        recent = now - timedelta(days=5)

        await _seed_chain(db_session, [old, recent])

        await AuditService.purge_expired_entries(db_session, retention_months=6)

        result = await db_session.execute(
            select(AuditLogEntry).where(AuditLogEntry.action_type == AuditActionType.AUDIT_PURGE.value)
        )
        marker = result.scalar_one()

        payload = {
            "sequence_number": marker.sequence_number,
            "timestamp": marker.timestamp.isoformat(),
            "actor_id": None,
            "actor_identity": marker.actor_identity,
            "action_type": marker.action_type,
            "resource_type": marker.resource_type,
            "resource_id": marker.resource_id,
            "outcome": marker.outcome,
            "context": marker.context,
        }
        expected_hash = _compute_row_hash(payload, marker.prev_hash)
        assert marker.row_hash == expected_hash, (
            f"Marker row_hash {marker.row_hash!r} is not the correct SHA-256 for its payload"
        )
