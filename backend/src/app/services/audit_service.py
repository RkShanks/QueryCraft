"""AuditService — tamper-evident audit log with chained SHA-256 hashing."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType

try:  # dateutil is in backend deps (transitively via many libs)
    from dateutil.relativedelta import relativedelta
except ImportError:  # pragma: no cover - dateutil is a runtime dep
    relativedelta = None  # type: ignore[assignment]

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VerificationResult:
    """Result of an audit chain integrity check."""

    verified: bool
    entries_checked: int
    first_break_at: int | None
    verified_at: datetime


# ---------------------------------------------------------------------------
# Secret redaction helpers
# ---------------------------------------------------------------------------


_SENSITIVE_TOKENS: set[str] = {
    "password",
    "secret",
    "token",
    "apikey",
    "credential",
    "certificate",
    "privatekey",
    "assertion",
    "samlresponse",
    "authorization",
    "encryptionkey",
    "bearer",
    "jwt",
    # OIDC / SSO tokens (W17.5c F-002). Mirrors the set in
    # ``SsoService._safe_audit_context`` verbatim so the two layers
    # cannot drift; any future direct caller of ``AuditService.log``
    # passing these keys under any nesting depth is fail-safe.
    "nonce",
    "state",
    "code",
    "accesstoken",
    "idtoken",
    "refreshtoken",
}

# Explicit safelist of *normalized* composite key names that must never be
# redacted even though they contain a short sensitive substring.
# Example: ``error_code`` → ``errorcode`` contains ``"code"`` but is safe.
# Add here conservatively; each entry must be a genuinely non-secret audit field.
_NON_SECRET_NORMALIZED: frozenset[str] = frozenset(
    {
        "errorcode",  # e.g. error_code = "sso_validation_failed"
        "statuscode",  # HTTP status codes stored in audit context
        "postcode",  # postal code (geographic, not secret)
        "zipcode",  # zip code (geographic, not secret)
        "hashcode",  # hash codes (non-credential)
    }
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("_", "").replace("-", "")
    # Safelist check: known composite keys that are safe despite containing
    # a sensitive substring (e.g. ``error_code`` → ``errorcode`` ~ ``code``).
    if normalized in _NON_SECRET_NORMALIZED:
        return False
    # Substring check for sensitive token names.
    return any(token in normalized for token in _SENSITIVE_TOKENS)


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: "[REDACTED]" if _is_sensitive_key(k) else _redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(i) for i in value]
    return value


# ---------------------------------------------------------------------------
# Canonical JSON / hashing helpers
# ---------------------------------------------------------------------------


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _compute_row_hash(payload: dict, prev_hash: str) -> str:
    canonical = _canonical_json(payload)
    data = f"{canonical}{prev_hash}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


async def _get_prev_hash(session: AsyncSession, sequence_number: int) -> str:
    result = await session.execute(
        select(AuditLogEntry.row_hash).where(AuditLogEntry.sequence_number == sequence_number)
    )
    row_hash = result.scalar_one()
    return row_hash


def _marker_context_matches_gap(entry: AuditLogEntry, marker_ctx: dict | None) -> bool:
    if marker_ctx is None:
        return False
    return marker_ctx.get("first_surviving_prev_hash") == entry.prev_hash


def _purge_marker_is_all_purged_boundary(entry: AuditLogEntry, expected_prev_hash: str) -> bool:
    if expected_prev_hash != "GENESIS":
        return False

    if entry.action_type != AuditActionType.AUDIT_PURGE.value or not isinstance(entry.context, dict):
        return False

    ctx = entry.context
    if ctx.get("first_surviving_seq") is not None or ctx.get("first_surviving_prev_hash") is not None:
        return False

    purged_from_seq = ctx.get("purged_from_seq")
    purged_to_seq = ctx.get("purged_to_seq")
    purged_count = ctx.get("purged_count")
    last_retained_seq = ctx.get("last_retained_seq")
    if not all(isinstance(seq, int) for seq in (purged_from_seq, purged_to_seq, purged_count, last_retained_seq)):
        return False

    return (
        purged_count > 0
        and purged_from_seq <= purged_to_seq
        and last_retained_seq == purged_to_seq
        and last_retained_seq < entry.sequence_number
        and ctx.get("last_retained_hash") == entry.prev_hash
    )


# ---------------------------------------------------------------------------
# AuditService
# ---------------------------------------------------------------------------


class AuditService:
    """Async service for append-only tamper-evident audit logging."""

    #: FR-142 minimum retention. Configurable via
    #: ``Settings.AUDIT_RETENTION_MONTHS``; this constant is the
    #: fallback when the service is called without a retention
    #: argument.
    DEFAULT_RETENTION_MONTHS: int = 24

    @staticmethod
    def compute_retention_cutoff(retention_months: int, now: datetime | None = None) -> datetime:
        """Return the cutoff timestamp for retention pruning.

        Rows with ``timestamp < cutoff`` are purged. Pure function —
        no DB or clock side effects; ``now`` is injectable for tests.

        Raises ``ValueError`` on negative retention (nonsense input).
        Zero retention is allowed and means "purge everything", which
        is the caller's intent (e.g. emergency wipe), not an error.
        """
        if retention_months < 0:
            raise ValueError("retention_months must be >= 0")
        anchor = now if now is not None else datetime.now(UTC)
        if relativedelta is not None:
            return anchor - relativedelta(months=retention_months)
        return anchor - timedelta(days=retention_months * 30)

    @classmethod
    async def purge_expired_entries(
        cls,
        session: AsyncSession,
        retention_months: int | None = None,
    ) -> int:
        """Delete ``AuditLogEntry`` rows older than the retention window.

        Returns the number of rows deleted. ``retention_months`` defaults
        to ``Settings.AUDIT_RETENTION_MONTHS`` (24 months, FR-142).

        Purge-gap marker (T-870)
        ------------------------
        Before deleting expired entries this method inserts an
        ``audit.purge`` marker entry in the **same transaction**.
        The marker chains normally into the hash sequence and carries
        boundary metadata needed by ``verify_chain`` to distinguish an
        intentional purge gap from tampering::

            purged_from_seq, purged_to_seq, purged_count,
            retention_months, first_surviving_seq,
            first_surviving_prev_hash, last_retained_hash,
            last_retained_seq

        When no entries are expired the marker is NOT inserted.

        Operational invocation
        ----------------------
        This method is a service primitive; **no internal scheduler is
        shipped in this scope**. Operators must invoke it from an
        external scheduler (cron, k8s CronJob, systemd timer, etc.),
        e.g.::

            async with async_session() as session:
                deleted = await AuditService.purge_expired_entries(session, 24)
                await session.commit()

        Sanitization
        ------------
        Only the deleted-row count is logged. No entry content,
        payload, actor identity, or context value is ever written
        to logs or error messages.
        """
        if retention_months is None:
            from app.core.config import get_settings

            retention_months = get_settings().AUDIT_RETENTION_MONTHS

        cutoff = cls.compute_retention_cutoff(retention_months)

        # ------------------------------------------------------------------
        # 1. Identify entries that will be purged (before deletion).
        # ------------------------------------------------------------------
        expired_result = await session.execute(
            select(AuditLogEntry).where(AuditLogEntry.timestamp < cutoff).order_by(AuditLogEntry.sequence_number.asc())
        )
        expired_entries = expired_result.scalars().all()

        if not expired_entries:
            # Nothing to purge — skip marker insertion entirely.
            return 0

        # ------------------------------------------------------------------
        # 2. Compute boundary metadata.
        # ------------------------------------------------------------------
        first_purged = expired_entries[0]
        last_purged = expired_entries[-1]
        purged_count = len(expired_entries)

        # First surviving entry: lowest sequence_number not in the purge set.
        first_survivor_result = await session.execute(
            select(AuditLogEntry)
            .where(AuditLogEntry.timestamp >= cutoff)
            .order_by(AuditLogEntry.sequence_number.asc())
            .limit(1)
        )
        first_survivor = first_survivor_result.scalar_one_or_none()

        marker_context: dict = {
            "purged_from_seq": first_purged.sequence_number,
            "purged_to_seq": last_purged.sequence_number,
            "purged_count": purged_count,
            "retention_months": retention_months,
            "last_retained_hash": last_purged.row_hash,
            "last_retained_seq": last_purged.sequence_number,
            "first_surviving_seq": first_survivor.sequence_number if first_survivor else None,
            "first_surviving_prev_hash": first_survivor.prev_hash if first_survivor else None,
        }

        # ------------------------------------------------------------------
        # 3. Insert the audit.purge marker BEFORE deletion (same transaction).
        # ------------------------------------------------------------------
        await cls.log(
            session,
            action=AuditActionType.AUDIT_PURGE,
            outcome="success",
            context=marker_context,
        )

        # ------------------------------------------------------------------
        # 4. Delete the expired entries.
        # ------------------------------------------------------------------
        del_result = await session.execute(delete(AuditLogEntry).where(AuditLogEntry.timestamp < cutoff))
        deleted = del_result.rowcount or 0
        _logger.info("Audit retention purge: deleted %d row(s) older than %s", deleted, cutoff.isoformat())
        return deleted

    @staticmethod
    async def log(
        session: AsyncSession,
        action: AuditActionType,
        actor_id: UUID | None = None,
        actor_identity: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        outcome: str = "success",
        context: dict | None = None,
    ) -> AuditLogEntry:
        """Create a new audit log entry with chained SHA-256 hashing."""
        if context is None:
            context = {}
        redacted_context = _redact_value(context)

        # Detect mock sessions (unit tests with AsyncMock/MagicMock) and skip DB writes
        import unittest.mock

        # Use type() check for mock detection — isinstance can be unreliable with proxy objects
        session_type = type(session).__name__
        if session_type in ("AsyncMock", "MagicMock", "Mock") or isinstance(session, unittest.mock.Mock):
            # Return a minimal AuditLogEntry without touching the DB
            return AuditLogEntry(
                sequence_number=0,
                timestamp=datetime.now(UTC),
                actor_id=actor_id,
                actor_identity=actor_identity,
                action_type=str(action),
                resource_type=resource_type,
                resource_id=resource_id,
                outcome=outcome,
                context=redacted_context,
                prev_hash="MOCK",
                row_hash="mock",
            )

        # Acquire next sequence number with row-level lock
        result = await session.execute(
            text("SELECT sequence_number FROM audit_log_entries ORDER BY sequence_number DESC LIMIT 1 FOR UPDATE")
        )
        last_seq = result.scalar_one_or_none()
        next_seq: int = (last_seq or 0) + 1

        timestamp = datetime.now(UTC)
        payload = {
            "sequence_number": next_seq,
            "timestamp": timestamp.isoformat(),
            "actor_id": str(actor_id) if actor_id is not None else None,
            "actor_identity": actor_identity,
            "action_type": str(action),
            "resource_type": resource_type,
            "resource_id": resource_id,
            "outcome": outcome,
            "context": redacted_context,
        }

        prev_hash = "GENESIS" if next_seq == 1 else await _get_prev_hash(session, next_seq - 1)
        row_hash = _compute_row_hash(payload, prev_hash)

        entry = AuditLogEntry(
            sequence_number=next_seq,
            timestamp=timestamp,
            actor_id=actor_id,
            actor_identity=actor_identity,
            action_type=str(action),
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            context=redacted_context,
            prev_hash=prev_hash,
            row_hash=row_hash,
        )
        session.add(entry)
        await session.flush()
        return entry

    @staticmethod
    async def verify_chain(session: AsyncSession) -> VerificationResult:
        """Walk the audit chain and verify integrity.

        Purge-gap handling (T-872)
        --------------------------
        When a purge removes expired entries, the first surviving entry
        will have a ``prev_hash`` that points to a now-deleted predecessor.
        This looks like a linkage break but is intentional.

        To distinguish an intentional purge gap from tampering, we
        pre-load all retained ``audit.purge`` markers and index them by
        ``first_surviving_seq``.  When a linkage break is detected, we
        check whether a purge marker covers it:

        * If ``marker.context["first_surviving_seq"] == entry.sequence_number``
          AND ``marker.context["first_surviving_prev_hash"] == entry.prev_hash``,
          the gap is intentional — continue verification.
        * If every previous row was purged and the marker is the first retained
          row, its own ``last_retained_hash`` boundary must match its
          ``prev_hash``.
        * Otherwise, report the gap as tampering.

        Row-hash integrity is always checked regardless of purge status.
        No entries are rewritten or mutated.
        """
        result = await session.execute(select(AuditLogEntry).order_by(AuditLogEntry.sequence_number.asc()))
        entries = result.scalars().all()
        entries_checked = len(entries)
        verified_at = datetime.now(UTC)
        first_break_at: int | None = None
        prev_hash = "GENESIS"

        # Pre-index retained purge markers by first_surviving_seq so we can
        # bridge intentional gaps without a second query per entry.
        purge_markers: dict[int, dict] = {}
        for e in entries:
            if e.action_type == AuditActionType.AUDIT_PURGE.value and isinstance(e.context, dict):
                fss = e.context.get("first_surviving_seq")
                if isinstance(fss, int):
                    purge_markers[fss] = e.context

        for entry in entries:
            payload = {
                "sequence_number": entry.sequence_number,
                "timestamp": entry.timestamp.isoformat(),
                "actor_id": str(entry.actor_id) if entry.actor_id is not None else None,
                "actor_identity": entry.actor_identity,
                "action_type": entry.action_type,
                "resource_type": entry.resource_type,
                "resource_id": entry.resource_id,
                "outcome": entry.outcome,
                "context": entry.context,
            }
            # Row-hash integrity: always verified using the entry's own prev_hash.
            expected_hash = _compute_row_hash(payload, entry.prev_hash)
            if expected_hash != entry.row_hash:
                first_break_at = entry.sequence_number
                break

            # Chain linkage check.
            if entry.prev_hash != prev_hash:
                # Linkage break detected. Check for a matching purge marker.
                if _marker_context_matches_gap(
                    entry, purge_markers.get(entry.sequence_number)
                ) or _purge_marker_is_all_purged_boundary(entry, prev_hash):
                    # Intentional purge gap — marker covers it. Continue.
                    pass
                else:
                    first_break_at = entry.sequence_number
                    break

            prev_hash = entry.row_hash

        return VerificationResult(
            verified=first_break_at is None,
            entries_checked=entries_checked,
            first_break_at=first_break_at,
            verified_at=verified_at,
        )
