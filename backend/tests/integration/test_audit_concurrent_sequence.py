"""Concurrent audit sequence allocation must remain gap-free and unique."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType
from app.services.audit_service import AuditService


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
async def test_waiting_writer_reloads_latest_sequence_after_allocator_lock(async_engine_fixture):
    session_factory = async_sessionmaker(
        async_engine_fixture,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as seed_session:
        await AuditService.log(
            seed_session,
            action=AuditActionType.AUTH_LOGIN_SUCCESS,
            outcome="success",
        )
        await seed_session.commit()

    first_session = session_factory()
    second_session = session_factory()
    second_task = None
    try:
        first = await AuditService.log(
            first_session,
            action=AuditActionType.QUERY_HISTORY_VIEW,
            outcome="success",
            context={"operation": "list"},
        )

        second_task = asyncio.create_task(
            AuditService.log(
                second_session,
                action=AuditActionType.QUERY_RERUN,
                outcome="success",
                context={},
            )
        )
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(second_task), timeout=0.1)

        await first_session.commit()
        second = await second_task
        await second_session.commit()

        assert (first.sequence_number, second.sequence_number) == (2, 3)

        async with session_factory() as verification_session:
            rows = list(
                (
                    await verification_session.execute(
                        select(AuditLogEntry).order_by(AuditLogEntry.sequence_number)
                    )
                )
                .scalars()
                .all()
            )
            verification = await AuditService.verify_chain(verification_session)

        assert [entry.sequence_number for entry in rows] == [1, 2, 3]
        assert verification.verified is True
    finally:
        if second_task is not None and not second_task.done():
            second_task.cancel()
        await first_session.rollback()
        await second_session.rollback()
        await first_session.close()
        await second_session.close()
        async with async_engine_fixture.begin() as connection:
            await connection.execute(text("TRUNCATE TABLE audit_log_entries"))
