"""Regression coverage for bounded audit-chain verification."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import event

from app.db.models.audit_log_entry import AuditLogEntry
from app.services.audit_service import AuditService, _compute_row_hash

_EXPECTED_BATCH_SIZE = 500
_LARGE_CHAIN_SIZE = (_EXPECTED_BATCH_SIZE * 2) + 1


def _audit_payload(sequence_number: int, timestamp: datetime) -> dict[str, Any]:
    return {
        "sequence_number": sequence_number,
        "timestamp": timestamp.isoformat(),
        "actor_id": None,
        "actor_identity": None,
        "action_type": "query.submit",
        "resource_type": None,
        "resource_id": None,
        "outcome": "success",
        "context": {},
    }


def _build_chain(entry_count: int) -> list[AuditLogEntry]:
    timestamp = datetime.now(UTC)
    entries: list[AuditLogEntry] = []
    previous_hash = "GENESIS"
    for sequence_number in range(1, entry_count + 1):
        row_hash = _compute_row_hash(
            _audit_payload(sequence_number, timestamp),
            previous_hash,
        )
        entries.append(
            AuditLogEntry(
                sequence_number=sequence_number,
                timestamp=timestamp,
                action_type="query.submit",
                outcome="success",
                context={},
                prev_hash=previous_hash,
                row_hash=row_hash,
            )
        )
        previous_hash = row_hash
    return entries


def _is_verification_entry_select(statement: str) -> bool:
    normalized = " ".join(statement.split()).lower()
    return (
        normalized.startswith("select audit_log_entries.id")
        and "order by audit_log_entries.sequence_number asc" in normalized
    )


def _parameter_values(parameters: Any) -> tuple[Any, ...]:
    if isinstance(parameters, dict):
        return tuple(parameters.values())
    if isinstance(parameters, (list, tuple)):
        return tuple(parameters)
    return (parameters,)


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
async def test_large_chain_verification_loads_only_bounded_keyset_batches(
    db_session,
    async_engine_fixture,
):
    """C6-M02: a retained chain larger than two batches never uses an unbounded SELECT."""
    db_session.add_all(_build_chain(_LARGE_CHAIN_SIZE))
    await db_session.flush()

    verification_selects: list[tuple[str, Any]] = []

    def record_verification_select(
        _connection,
        _cursor,
        statement,
        parameters,
        _context,
        _executemany,
    ) -> None:
        if _is_verification_entry_select(statement):
            verification_selects.append((statement, parameters))

    event.listen(
        async_engine_fixture.sync_engine,
        "before_cursor_execute",
        record_verification_select,
    )
    try:
        verification = await AuditService.verify_chain(db_session)
    finally:
        event.remove(
            async_engine_fixture.sync_engine,
            "before_cursor_execute",
            record_verification_select,
        )

    assert verification.verified is True
    assert verification.entries_checked == _LARGE_CHAIN_SIZE
    assert len(verification_selects) == 3
    for statement, parameters in verification_selects:
        normalized = " ".join(statement.split()).lower()
        assert "audit_log_entries.sequence_number >" in normalized
        assert "audit_log_entries.sequence_number <=" in normalized
        assert " limit " in normalized
        assert _EXPECTED_BATCH_SIZE in _parameter_values(parameters)
