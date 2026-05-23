"""Tests for audit entry immutability (T-622)."""


import pytest
from app.services.audit_service import AuditService
from sqlalchemy import delete, update

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType


@pytest.mark.asyncio
class TestAuditImmutability:
    """Application-layer prevention of UPDATE/DELETE on audit log entries."""

    async def test_orm_update_raises(self, db_session):
        entry = await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.commit()

        entry.outcome = "tampered"
        with pytest.raises(RuntimeError):
            await db_session.commit()

    async def test_orm_delete_raises(self, db_session):
        entry = await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.commit()

        await db_session.delete(entry)
        with pytest.raises(RuntimeError):
            await db_session.commit()

    async def test_raw_update_blocked(self, db_session):
        entry = await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.commit()

        with pytest.raises(RuntimeError):
            await db_session.execute(
                update(AuditLogEntry)
                .where(AuditLogEntry.sequence_number == entry.sequence_number)
                .values(outcome="tampered")
            )
            await db_session.commit()

    async def test_raw_delete_blocked(self, db_session):
        entry = await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.commit()

        with pytest.raises(RuntimeError):
            await db_session.execute(
                delete(AuditLogEntry).where(AuditLogEntry.sequence_number == entry.sequence_number)
            )
            await db_session.commit()

    async def test_no_update_method_on_service(self):
        assert not hasattr(AuditService, "update")
        assert not hasattr(AuditService, "delete")
