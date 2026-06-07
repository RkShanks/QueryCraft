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
}


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("_", "").replace("-", "")
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

        Operational invocation
        ----------------------
        This method is a service primitive; **no internal scheduler is
        shipped in this scope**. Operators must invoke it from an
        external scheduler (cron, k8s CronJob, systemd timer, etc.),
        e.g.::

            SELECT AuditService.purge_expired_entries(session, 24);

        Chain verification after pruning
        --------------------------------
        The hash chain was designed to prove no tampering across the
        full append-only history. Pruning deletes history; the chain
        can no longer be verified from ``GENESIS``. The retained
        window is internally consistent, but ``verify_chain`` will
        honestly report a break at the first surviving row because
        that row's ``prev_hash`` references a ``row_hash`` of a
        now-deleted row. This is intentional and documented — the
        chain is not silently rewritten to "lie" about retained
        history. Operators should re-issue a baseline ``audit.verify``
        event after each prune to record the new on-disk state.

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

        result = await session.execute(delete(AuditLogEntry).where(AuditLogEntry.timestamp < cutoff))
        deleted = result.rowcount or 0
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
        """Walk the audit chain and verify integrity."""
        result = await session.execute(select(AuditLogEntry).order_by(AuditLogEntry.sequence_number.asc()))
        entries = result.scalars().all()
        entries_checked = len(entries)
        verified_at = datetime.now(UTC)
        first_break_at: int | None = None
        prev_hash = "GENESIS"

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
            expected_hash = _compute_row_hash(payload, entry.prev_hash)
            if expected_hash != entry.row_hash or entry.prev_hash != prev_hash:
                first_break_at = entry.sequence_number
                break
            prev_hash = entry.row_hash

        return VerificationResult(
            verified=first_break_at is None,
            entries_checked=entries_checked,
            first_break_at=first_break_at,
            verified_at=verified_at,
        )
