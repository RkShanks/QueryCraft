"""Tests for AuditService (T-619)."""

from datetime import datetime
from uuid import uuid4

import pytest
from app.services.audit_service import AuditService, VerificationResult
from sqlalchemy import select

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType


@pytest.mark.asyncio
class TestAuditService:
    """AuditService TDD: log, chain hashing, genesis, canonical JSON."""

    async def test_log_creates_entry(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            actor_id=uuid4(),
            actor_identity="alice",
            resource_type="query",
            resource_id="q-1",
            outcome="success",
            context={"question": "test"},
        )
        assert entry.sequence_number == 1
        assert entry.action_type == "query.submit"
        assert entry.actor_identity == "alice"
        assert entry.prev_hash == "GENESIS"
        assert entry.row_hash

    async def test_log_assigns_increasing_sequence(self, db_session):
        e1 = await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)
        e2 = await AuditService.log(db_session, action=AuditActionType.QUERY_EXECUTE)
        assert e1.sequence_number == 1
        assert e2.sequence_number == 2

    async def test_log_prev_hash_chains(self, db_session):
        e1 = await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)
        e2 = await AuditService.log(db_session, action=AuditActionType.QUERY_EXECUTE)
        assert e2.prev_hash == e1.row_hash

    async def test_log_row_hash_is_sha256(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.AUTH_LOGIN_SUCCESS,
            actor_identity="admin",
            outcome="success",
            context={},
        )
        assert len(entry.row_hash) == 64
        assert all(c in "0123456789abcdef" for c in entry.row_hash)

    async def test_log_returns_verification_result_type(self, db_session):
        result = await AuditService.verify_chain(db_session)
        assert isinstance(result, VerificationResult)
        assert isinstance(result.verified, bool)
        assert isinstance(result.entries_checked, int)
        assert result.first_break_at is None or isinstance(result.first_break_at, int)
        assert isinstance(result.verified_at, datetime)

    async def test_log_canonical_json_no_whitespace(self, db_session):
        # Insert entry with nested dict; verify row_hash matches expected canonical form
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            context={"b": 2, "a": 1},
        )
        # Recompute manually with sorted keys and no whitespace
        import hashlib
        import json

        ts = entry.timestamp.isoformat()
        payload = {
            "sequence_number": entry.sequence_number,
            "timestamp": ts,
            "actor_id": None,
            "actor_identity": None,
            "action_type": "query.submit",
            "resource_type": None,
            "resource_id": None,
            "outcome": "success",
            "context": {"a": 1, "b": 2},
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        expected = hashlib.sha256(f"{canonical}{entry.prev_hash}".encode()).hexdigest()
        assert entry.row_hash == expected

    async def test_log_populates_db(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            actor_identity="bob",
        )
        await db_session.commit()
        result = await db_session.execute(
            select(AuditLogEntry).where(AuditLogEntry.sequence_number == entry.sequence_number)
        )
        fetched = result.scalar_one()
        assert fetched.actor_identity == "bob"
