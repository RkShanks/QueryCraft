"""Tests for AuditLogEntry ORM model (T-615)."""

from uuid import uuid4

from sqlalchemy import BigInteger, String
from sqlalchemy.dialects.postgresql import JSONB

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType


class TestAuditLogEntryModel:
    """AuditLogEntry ORM model metadata and instantiation."""

    def test_table_name(self):
        assert AuditLogEntry.__tablename__ == "audit_log_entries"

    def test_can_instantiate(self):
        entry = AuditLogEntry(
            sequence_number=1,
            actor_id=uuid4(),
            actor_identity="admin",
            action_type=AuditActionType.AUTH_LOGIN_SUCCESS,
            resource_type="session",
            resource_id="sess-1",
            outcome="success",
            context={"ip": "127.0.0.1"},
            prev_hash="GENESIS",
            row_hash="abc123",
        )
        assert entry.sequence_number == 1
        assert entry.outcome == "success"

    def test_sequence_number_column_type(self):
        assert isinstance(AuditLogEntry.__table__.c.sequence_number.type, BigInteger)

    def test_prev_hash_column(self):
        assert isinstance(AuditLogEntry.__table__.c.prev_hash.type, String)

    def test_row_hash_column(self):
        assert isinstance(AuditLogEntry.__table__.c.row_hash.type, String)

    def test_context_jsonb(self):
        assert isinstance(AuditLogEntry.__table__.c.context.type, JSONB)

    def test_sequence_number_unique(self):
        assert AuditLogEntry.__table__.c.sequence_number.unique is True
