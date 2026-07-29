"""Regression coverage for bounded audit-chain verification."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType
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


def _build_chain(
    entry_count: int,
    first_timestamp: datetime | None = None,
) -> list[AuditLogEntry]:
    current_timestamp = datetime.now(UTC)
    entries: list[AuditLogEntry] = []
    previous_hash = "GENESIS"
    for sequence_number in range(1, entry_count + 1):
        timestamp = first_timestamp if sequence_number == 1 and first_timestamp is not None else current_timestamp
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


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
async def test_tamper_at_second_batch_start_reports_exact_first_break(db_session):
    """A row-hash break at the keyset boundary remains the exact reported break."""
    db_session.add_all(_build_chain(_EXPECTED_BATCH_SIZE + 1))
    await db_session.flush()
    await db_session.execute(
        text(
            """
            UPDATE audit_log_entries
            SET row_hash = :tampered_hash
            WHERE sequence_number = :sequence_number
            """
        ),
        {
            "tampered_hash": "0" * 64,
            "sequence_number": _EXPECTED_BATCH_SIZE + 1,
        },
    )

    verification = await AuditService.verify_chain(db_session)

    assert verification.verified is False
    assert verification.entries_checked == _EXPECTED_BATCH_SIZE + 1
    assert verification.first_break_at == _EXPECTED_BATCH_SIZE + 1


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
async def test_purge_marker_in_later_batch_bridges_first_survivor_gap(db_session):
    """A valid marker beyond the first batch still covers the retained prefix gap."""
    chain = _build_chain(_EXPECTED_BATCH_SIZE + 1)
    db_session.add_all(chain)
    await db_session.flush()
    await db_session.execute(
        text(
            """
            UPDATE audit_log_entries
            SET timestamp = :expired_at
            WHERE sequence_number = 1
            """
        ),
        {"expired_at": datetime.now(UTC) - timedelta(days=400)},
    )

    deleted = await AuditService.purge_expired_entries(
        db_session,
        retention_months=6,
    )
    verification = await AuditService.verify_chain(db_session)

    assert deleted == 1
    assert verification.verified is True
    assert verification.entries_checked == _EXPECTED_BATCH_SIZE + 1
    assert verification.first_break_at is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
async def test_concurrent_append_cannot_extend_verification_snapshot(
    async_engine_fixture,
):
    """An append waits behind verification and lands after its upper boundary."""
    session_factory = async_sessionmaker(
        async_engine_fixture,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as seed_session:
        seed_session.add_all(_build_chain(_EXPECTED_BATCH_SIZE + 1))
        await seed_session.commit()

    verification_session = session_factory()
    append_session = session_factory()
    append_task = None
    try:
        verification = await AuditService.verify_chain(verification_session)
        append_task = asyncio.create_task(
            AuditService.log(
                append_session,
                action=AuditActionType.QUERY_SUBMIT,
            )
        )
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(append_task), timeout=0.1)

        assert verification.verified is True
        assert verification.entries_checked == _EXPECTED_BATCH_SIZE + 1

        await verification_session.commit()
        appended_entry = await append_task
        await append_session.commit()

        assert appended_entry.sequence_number == _EXPECTED_BATCH_SIZE + 2
    finally:
        if append_task is not None and not append_task.done():
            append_task.cancel()
            with suppress(asyncio.CancelledError):
                await append_task
        await verification_session.rollback()
        await append_session.rollback()
        await verification_session.close()
        await append_session.close()


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
async def test_concurrent_purge_waits_for_bounded_verification(
    async_engine_fixture,
):
    """Purge cannot delete a retained row while its verification snapshot is active."""
    session_factory = async_sessionmaker(
        async_engine_fixture,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as seed_session:
        seed_session.add_all(
            _build_chain(
                _EXPECTED_BATCH_SIZE + 1,
                first_timestamp=datetime.now(UTC) - timedelta(days=400),
            )
        )
        await seed_session.commit()

    verification_session = session_factory()
    purge_session = session_factory()
    purge_task = None
    try:
        verification = await AuditService.verify_chain(verification_session)
        purge_task = asyncio.create_task(
            AuditService.purge_expired_entries(
                purge_session,
                retention_months=6,
            )
        )
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(purge_task), timeout=0.1)

        assert verification.verified is True
        assert verification.entries_checked == _EXPECTED_BATCH_SIZE + 1

        await verification_session.commit()
        deleted = await purge_task
        await purge_session.commit()

        assert deleted == 1
        async with session_factory() as post_purge_session:
            post_purge_verification = await AuditService.verify_chain(post_purge_session)
            assert post_purge_verification.verified is True
            assert post_purge_verification.entries_checked == _EXPECTED_BATCH_SIZE + 1
    finally:
        if purge_task is not None and not purge_task.done():
            purge_task.cancel()
            with suppress(asyncio.CancelledError):
                await purge_task
        await verification_session.rollback()
        await purge_session.rollback()
        await verification_session.close()
        await purge_session.close()
