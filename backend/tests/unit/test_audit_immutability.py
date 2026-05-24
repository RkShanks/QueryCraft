"""Tests for audit entry immutability (T-622)."""

import pytest

from app.db.models.enums import AuditActionType
from app.services.audit_service import AuditService


@pytest.mark.asyncio
class TestAuditImmutability:
    """Application-layer prevention of UPDATE/DELETE on audit log entries."""

    async def test_orm_update_raises(self, db_session):
        entry = await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.flush()

        entry.outcome = "tampered"
        with pytest.raises(RuntimeError):
            await db_session.flush()

    async def test_orm_delete_raises(self, db_session):
        entry = await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.flush()

        await db_session.delete(entry)
        with pytest.raises(RuntimeError):
            await db_session.flush()

    async def test_no_update_method_on_service(self):
        assert not hasattr(AuditService, "update")
        assert not hasattr(AuditService, "delete")
