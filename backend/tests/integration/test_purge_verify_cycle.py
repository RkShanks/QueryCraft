"""RED integration test for full purge+verify cycle (T-873).

Exercises the end-to-end path:

1. Seed audit entries with old (expired) + recent (retained) timestamps
   using the real AuditService.log() so hashes chain correctly.
2. Call AuditService.purge_expired_entries() — deletes expired entries
   and inserts the audit.purge marker in the same transaction.
3. Verify the audit.purge marker exists with all required boundary
   metadata fields and correct values.
4. Call AuditService.verify_chain() — must return verified=True because
   the purge marker covers the gap intentionally.
5. Append a new audit entry after the purge.
6. Call verify_chain() again — full retained chain (surviving entry +
   marker + new entry) must still verify end-to-end.

FR/SC: FR-166, FR-167, FR-172, FR-173, SC-069, SC-070, SC-077
Depends on: T-872 (verify_chain purge-gap handling), T-870 (purge marker)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType
from app.services.audit_service import AuditService

# ---------------------------------------------------------------------------
# Required boundary metadata keys from the purge marker (T-870 contract)
# ---------------------------------------------------------------------------

_REQUIRED_MARKER_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "purged_from_seq",
        "purged_to_seq",
        "purged_count",
        "retention_months",
        "first_surviving_seq",
        "first_surviving_prev_hash",
        "last_retained_hash",
        "last_retained_seq",
    }
)

_RETENTION_MONTHS = 6  # purge window used throughout this module


# ---------------------------------------------------------------------------
# Helper: seed a chain of entries via AuditService.log (real hashes)
# ---------------------------------------------------------------------------


async def _log_entry(
    db_session,
    action: AuditActionType = AuditActionType.QUERY_SUBMIT,
    actor_identity: str | None = None,
) -> AuditLogEntry:
    """Insert one real audit entry via AuditService.log and flush."""
    return await AuditService.log(
        db_session,
        action=action,
        actor_identity=actor_identity,
        outcome="success",
        context={},
    )


# ---------------------------------------------------------------------------
# T-873 — Full purge+verify cycle (integration, requires live DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestPurgeVerifyCycleIntegration:
    """Full end-to-end purge+verify cycle with a real DB session.

    Each test starts from a clean audit_log_entries table (clean_audit_table
    fixture), seeds entries via AuditService.log, performs a purge, and
    exercises verify_chain in the scenarios documented by T-873.
    """

    # ------------------------------------------------------------------
    # T-873.1 — Basic cycle: old entries purged, marker inserted, chain ok
    # ------------------------------------------------------------------

    async def test_purge_inserts_marker_and_chain_verifies(self, db_session):
        """Core cycle: purge expired entries → marker present → chain verified.

        Scenario
        --------
        * seed seq=1 (old, will be purged)
        * seed seq=2 (recent, survives)
        * purge_expired_entries(retention=6 months) deletes seq=1,
          inserts audit.purge marker at seq=3
        * verify_chain() must return verified=True
        """
        now = datetime.now(UTC)

        # Seed two entries via real AuditService.log so hashes chain correctly.
        # We override their timestamps via direct SQL after seeding so that the
        # purge cutoff sees the old entry.  AuditService.log uses datetime.now(UTC)
        # internally; we backdate using a raw UPDATE after flush/commit.
        old_entry = await _log_entry(db_session, actor_identity="user-old")
        recent_entry = await _log_entry(db_session, actor_identity="user-recent")
        await db_session.flush()

        # Backdate old_entry so it falls outside the 6-month retention window.
        old_ts = now - timedelta(days=400)
        await db_session.execute(
            select(AuditLogEntry).where(AuditLogEntry.sequence_number == old_entry.sequence_number)
        )
        # Direct UPDATE via text; we need to mark it as old for purge to pick it up.
        from sqlalchemy import text

        await db_session.execute(
            text("UPDATE audit_log_entries SET timestamp = :ts WHERE sequence_number = :seq"),
            {"ts": old_ts, "seq": old_entry.sequence_number},
        )
        await db_session.flush()

        # --- Step 2: Purge ---
        deleted = await AuditService.purge_expired_entries(db_session, retention_months=_RETENTION_MONTHS)
        assert deleted == 1, f"Expected 1 deleted entry, got {deleted}"

        # --- Step 3: Verify audit.purge marker exists ---
        result = await db_session.execute(
            select(AuditLogEntry).where(AuditLogEntry.action_type == AuditActionType.AUDIT_PURGE.value)
        )
        marker = result.scalar_one_or_none()
        assert marker is not None, "Expected audit.purge marker to be present after purge"

        # --- Step 3b: Marker boundary metadata is correct ---
        missing_keys = _REQUIRED_MARKER_CONTEXT_KEYS - set(marker.context.keys())
        assert not missing_keys, f"Marker context missing required keys: {missing_keys}"

        assert marker.context["purged_count"] == 1
        assert marker.context["retention_months"] == _RETENTION_MONTHS
        assert marker.context["purged_from_seq"] == old_entry.sequence_number
        assert marker.context["purged_to_seq"] == old_entry.sequence_number
        assert marker.context["first_surviving_seq"] == recent_entry.sequence_number
        # first_surviving_prev_hash must be the prev_hash of the surviving entry
        # (which points to the now-deleted old entry's row_hash)
        assert marker.context["first_surviving_prev_hash"] == recent_entry.prev_hash
        assert marker.context["last_retained_hash"] == old_entry.row_hash
        assert marker.context["last_retained_seq"] == old_entry.sequence_number

        # --- Step 4: verify_chain() returns verified=True ---
        verify_result = await AuditService.verify_chain(db_session)
        assert verify_result.verified is True, (
            f"verify_chain must return verified=True after purge with valid marker; "
            f"first_break_at={verify_result.first_break_at!r}"
        )
        assert verify_result.first_break_at is None

    # ------------------------------------------------------------------
    # T-873.2 — Marker boundary metadata correctness with multiple purged entries
    # ------------------------------------------------------------------

    async def test_marker_boundary_metadata_multiple_purged_entries(self, db_session):
        """Marker context is correct when several entries are purged.

        Scenario
        --------
        * seed seq=1,2,3 (all old, will be purged)
        * seed seq=4 (recent, survives)
        * purge_expired_entries deletes seq=1..3, inserts marker at seq=5
        * Marker must record purged_from_seq=1, purged_to_seq=3, purged_count=3
        * first_surviving_seq=4, last_retained_seq=3
        """
        from sqlalchemy import text

        now = datetime.now(UTC)
        old_ts = now - timedelta(days=400)

        # Log four entries (chain seq=1..4)
        e1 = await _log_entry(db_session, actor_identity="user-a")
        e2 = await _log_entry(db_session, actor_identity="user-b")
        e3 = await _log_entry(db_session, actor_identity="user-c")
        e4 = await _log_entry(db_session, actor_identity="user-d")
        await db_session.flush()

        # Backdate the first three entries
        for old_entry in (e1, e2, e3):
            await db_session.execute(
                text("UPDATE audit_log_entries SET timestamp = :ts WHERE sequence_number = :seq"),
                {"ts": old_ts, "seq": old_entry.sequence_number},
            )
        await db_session.flush()

        deleted = await AuditService.purge_expired_entries(db_session, retention_months=_RETENTION_MONTHS)
        assert deleted == 3, f"Expected 3 deleted, got {deleted}"

        result = await db_session.execute(
            select(AuditLogEntry).where(AuditLogEntry.action_type == AuditActionType.AUDIT_PURGE.value)
        )
        marker = result.scalar_one_or_none()
        assert marker is not None, "Purge marker must be inserted"

        # Check all 8 required keys present
        missing = _REQUIRED_MARKER_CONTEXT_KEYS - set(marker.context.keys())
        assert not missing, f"Marker missing keys: {missing}"

        # Boundary values
        assert marker.context["purged_from_seq"] == e1.sequence_number
        assert marker.context["purged_to_seq"] == e3.sequence_number
        assert marker.context["purged_count"] == 3
        assert marker.context["retention_months"] == _RETENTION_MONTHS
        assert marker.context["first_surviving_seq"] == e4.sequence_number
        assert marker.context["first_surviving_prev_hash"] == e4.prev_hash
        assert marker.context["last_retained_hash"] == e3.row_hash
        assert marker.context["last_retained_seq"] == e3.sequence_number

        # verify_chain must still return True
        vr = await AuditService.verify_chain(db_session)
        assert vr.verified is True, (
            f"verify_chain must be True with multiple-entry purge gap; first_break_at={vr.first_break_at!r}"
        )

    # ------------------------------------------------------------------
    # T-873.3 — Append new entry after purge → chain still valid end-to-end
    # ------------------------------------------------------------------

    async def test_new_entry_after_purge_chain_valid_end_to_end(self, db_session):
        """After purge, appending a new entry preserves end-to-end chain validity.

        Scenario
        --------
        * seed seq=1 (old), seq=2 (recent)
        * purge → marker at seq=3
        * log one more entry → seq=4
        * verify_chain() must return verified=True across all retained entries
          (seq=2, seq=3 marker, seq=4)
        """
        from sqlalchemy import text

        now = datetime.now(UTC)
        old_ts = now - timedelta(days=400)

        e1 = await _log_entry(db_session, actor_identity="user-x")
        e2 = await _log_entry(db_session, actor_identity="user-y")
        await db_session.flush()

        await db_session.execute(
            text("UPDATE audit_log_entries SET timestamp = :ts WHERE sequence_number = :seq"),
            {"ts": old_ts, "seq": e1.sequence_number},
        )
        await db_session.flush()

        deleted = await AuditService.purge_expired_entries(db_session, retention_months=_RETENTION_MONTHS)
        assert deleted == 1

        # Append a new entry after purge
        e_post = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            actor_identity="user-z",
            outcome="success",
            context={"note": "post-purge entry"},
        )
        await db_session.flush()

        assert e_post.sequence_number > e2.sequence_number, (
            "Post-purge entry must have a higher sequence_number than the surviving entry"
        )

        # Full end-to-end chain verification
        vr = await AuditService.verify_chain(db_session)
        assert vr.verified is True, (
            f"Chain must verify end-to-end after purge + new entry; first_break_at={vr.first_break_at!r}"
        )
        assert vr.first_break_at is None
        # Surviving entry + marker + post-purge entry = 3 entries checked
        assert vr.entries_checked == 3, (
            f"Expected 3 entries checked (survivor + marker + new), got {vr.entries_checked}"
        )

    # ------------------------------------------------------------------
    # T-873.4 — No marker, no purge when nothing is expired
    # ------------------------------------------------------------------

    async def test_no_purge_no_marker_chain_still_valid(self, db_session):
        """When no entries are expired, purge inserts no marker and chain verifies.

        Scenario
        --------
        * seed seq=1, seq=2 (both recent, neither expired)
        * purge_expired_entries → deletes=0, no marker inserted
        * verify_chain() must return verified=True
        """
        now = datetime.now(UTC)
        _ = now  # referenced for documentation clarity

        await _log_entry(db_session, actor_identity="user-p")
        await _log_entry(db_session, actor_identity="user-q")
        await db_session.flush()

        deleted = await AuditService.purge_expired_entries(db_session, retention_months=_RETENTION_MONTHS)
        assert deleted == 0, f"Expected 0 deleted (all entries are recent), got {deleted}"

        # No purge marker should exist
        result = await db_session.execute(
            select(AuditLogEntry).where(AuditLogEntry.action_type == AuditActionType.AUDIT_PURGE.value)
        )
        marker = result.scalar_one_or_none()
        assert marker is None, "No purge marker must be inserted when nothing is purged"

        # Chain must still verify cleanly
        vr = await AuditService.verify_chain(db_session)
        assert vr.verified is True
        assert vr.first_break_at is None

    # ------------------------------------------------------------------
    # T-873.5 — verify_chain correctly counts entries after purge
    # ------------------------------------------------------------------

    async def test_entries_checked_count_after_purge(self, db_session):
        """verify_chain.entries_checked reflects only retained entries after purge.

        Scenario
        --------
        * seed seq=1 (old, purged), seq=2 (recent, retained)
        * purge → seq=1 deleted, marker at seq=3
        * entries_checked == 2 (surviving entry seq=2 + marker seq=3)
        """
        from sqlalchemy import text

        now = datetime.now(UTC)
        old_ts = now - timedelta(days=400)

        e1 = await _log_entry(db_session)
        _e2 = await _log_entry(db_session)
        await db_session.flush()

        await db_session.execute(
            text("UPDATE audit_log_entries SET timestamp = :ts WHERE sequence_number = :seq"),
            {"ts": old_ts, "seq": e1.sequence_number},
        )
        await db_session.flush()

        await AuditService.purge_expired_entries(db_session, retention_months=_RETENTION_MONTHS)

        vr = await AuditService.verify_chain(db_session)
        assert vr.verified is True
        assert vr.entries_checked == 2, f"Expected 2 entries checked (survivor + marker), got {vr.entries_checked}"

    async def test_all_entries_purged_marker_only_chain_stays_valid_after_append(self, db_session):
        """Purging every existing entry leaves a marker boundary that still verifies."""
        from sqlalchemy import text

        now = datetime.now(UTC)
        old_ts = now - timedelta(days=400)

        e1 = await _log_entry(db_session, actor_identity="user-all-old-a")
        e2 = await _log_entry(db_session, actor_identity="user-all-old-b")
        await db_session.flush()

        for old_entry in (e1, e2):
            await db_session.execute(
                text("UPDATE audit_log_entries SET timestamp = :ts WHERE sequence_number = :seq"),
                {"ts": old_ts, "seq": old_entry.sequence_number},
            )
        await db_session.flush()

        deleted = await AuditService.purge_expired_entries(db_session, retention_months=_RETENTION_MONTHS)
        assert deleted == 2

        marker_result = await db_session.execute(
            select(AuditLogEntry).where(AuditLogEntry.action_type == AuditActionType.AUDIT_PURGE.value)
        )
        marker = marker_result.scalar_one()
        assert marker.context["first_surviving_seq"] is None
        assert marker.context["first_surviving_prev_hash"] is None
        assert marker.context["last_retained_hash"] == e2.row_hash

        verify_after_purge = await AuditService.verify_chain(db_session)
        assert verify_after_purge.verified is True
        assert verify_after_purge.entries_checked == 1

        await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            actor_identity="user-after-all-purged",
            outcome="success",
            context={},
        )
        await db_session.flush()

        verify_after_append = await AuditService.verify_chain(db_session)
        assert verify_after_append.verified is True
        assert verify_after_append.first_break_at is None
        assert verify_after_append.entries_checked == 2
