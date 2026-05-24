"""AuditService — tamper-evident audit log with chained SHA-256 hashing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType


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

_SENSITIVE_KEYS: set[str] = {
    "password",
    "secret",
    "token",
    "apikey",
    "credential",
    "clientsecret",
    "accesstoken",
    "refreshtoken",
    "certificate",
    "privatekey",
    "encryptionkey",
}


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("_", "").replace("-", "")
    return normalized in _SENSITIVE_KEYS


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
