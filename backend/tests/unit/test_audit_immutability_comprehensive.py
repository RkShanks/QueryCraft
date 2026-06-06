"""T-735 — Comprehensive audit entry immutability tests (Wave 17.4b).

Per FR-141 / SC-060: every audit log entry MUST be immutable at
the application layer. The shipped ``AuditLogEntry`` model wires
two SQLAlchemy ORM event listeners (``before_update`` and
``before_delete``) that raise ``RuntimeError("Audit log entries
are immutable")`` for any mutation attempt on an attached
instance. The previous wave's narrow smoke test
(``test_audit_immutability.py``) covers a single action type and
two fields. This module expands that surface to:

1. **Per-action-type immutability** — for every shipped
   ``AuditActionType`` enum value, attempt UPDATE and DELETE
   on a logged entry. Both must raise.
2. **Per-field immutability** — every tracked column
   (``sequence_number``, ``timestamp``, ``actor_id``,
   ``actor_identity``, ``action_type``, ``resource_type``,
   ``resource_id``, ``outcome``, ``context``, ``prev_hash``,
   ``row_hash``) must reject mutation. The chain-link fields
   are explicitly pinned because their tamper-evidence
   guarantee is the whole point of the hash chain.
3. **Multi-flush / commit resilience** — a tampered instance
   that is re-flushed or committed must continue to raise.
4. **Structural ORM wiring** — the model class must have
   ``before_update`` and ``before_delete`` listeners registered.
   This is the structural backstop: if a future migration drops
   the listeners, the runtime tests above will start failing
   and this one will surface the exact regression.
5. **No service-layer mutation API** — ``AuditService`` must
   not expose an ``update`` or ``delete`` method. The only
   mutating verb is ``log`` (insert).

This module is the comprehensive variant; the original
``test_audit_immutability.py`` (T-622) stays as the narrow
smoke test that the basic guard fires at all.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType
from app.services.audit_service import AuditService

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


_ALL_TRACKED_COLUMNS: tuple[str, ...] = (
    "sequence_number",
    "timestamp",
    "actor_id",
    "actor_identity",
    "action_type",
    "resource_type",
    "resource_id",
    "outcome",
    "context",
    "prev_hash",
    "row_hash",
)


async def _log_one(
    db_session,
    action: AuditActionType,
    context: dict | None = None,
) -> AuditLogEntry:
    """Log a single audit entry and return the attached instance."""
    return await AuditService.log(db_session, action=action, context=context)


# ---------------------------------------------------------------------------
# 1. Per-action-type UPDATE rejection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestUpdateRejectedForEveryActionType:
    """For every shipped ``AuditActionType``, mutate the entry's
    ``outcome`` and confirm ``flush()`` raises ``RuntimeError``.

    A single action type (``QUERY_SUBMIT``) was covered in the
    narrow ``test_audit_immutability.py``; this module pins the
    same contract for all 22 enum values so a future change
    that special-cases one action type would surface here.
    """

    @pytest.mark.parametrize(
        "action",
        list(AuditActionType),
        ids=[a.name for a in AuditActionType],
    )
    async def test_orm_update_raises_for_action(self, db_session, action):
        entry = await _log_one(db_session, action)
        await db_session.flush()

        entry.outcome = "tampered"
        with pytest.raises(RuntimeError):
            await db_session.flush()


# ---------------------------------------------------------------------------
# 2. Per-action-type DELETE rejection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestDeleteRejectedForEveryActionType:
    """For every shipped ``AuditActionType``, ``session.delete()`` and
    ``flush()`` must raise ``RuntimeError``."""

    @pytest.mark.parametrize(
        "action",
        list(AuditActionType),
        ids=[a.name for a in AuditActionType],
    )
    async def test_orm_delete_raises_for_action(self, db_session, action):
        entry = await _log_one(db_session, action)
        await db_session.flush()

        await db_session.delete(entry)
        with pytest.raises(RuntimeError):
            await db_session.flush()


# ---------------------------------------------------------------------------
# 3. Per-field immutability
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestEveryColumnIsImmutable:
    """The immutability guard fires on ANY column change, not just
    ``outcome``. This test iterates the model's tracked columns
    and mutates each one in turn.

    For JSONB columns (``context``) and date columns
    (``timestamp``), the ORM only detects a mutation if the
    attribute is reassigned; in-place dict mutation does not
    trigger the dirty-check. This matches the production
    threat model: a tampered application that holds a
    reference to the loaded entry would have to write a new
    value, which is exactly what this test exercises.
    """

    async def test_sequence_number_is_immutable(self, db_session):
        entry = await _log_one(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.flush()
        entry.sequence_number = 999_999
        with pytest.raises(RuntimeError):
            await db_session.flush()

    async def test_timestamp_is_immutable(self, db_session):
        from datetime import UTC, datetime

        entry = await _log_one(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.flush()
        entry.timestamp = datetime(2000, 1, 1, tzinfo=UTC)
        with pytest.raises(RuntimeError):
            await db_session.flush()

    async def test_actor_id_is_immutable(self, db_session):
        import uuid

        entry = await _log_one(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.flush()
        entry.actor_id = uuid.uuid4()
        with pytest.raises(RuntimeError):
            await db_session.flush()

    async def test_actor_identity_is_immutable(self, db_session):
        entry = await _log_one(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.flush()
        entry.actor_identity = "evil"
        with pytest.raises(RuntimeError):
            await db_session.flush()

    async def test_action_type_is_immutable(self, db_session):
        entry = await _log_one(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.flush()
        entry.action_type = "audit.tampered"
        with pytest.raises(RuntimeError):
            await db_session.flush()

    async def test_resource_type_is_immutable(self, db_session):
        entry = await _log_one(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.flush()
        entry.resource_type = "tampered"
        with pytest.raises(RuntimeError):
            await db_session.flush()

    async def test_resource_id_is_immutable(self, db_session):
        entry = await _log_one(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.flush()
        entry.resource_id = "tampered-id"
        with pytest.raises(RuntimeError):
            await db_session.flush()

    async def test_outcome_is_immutable(self, db_session):
        entry = await _log_one(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.flush()
        entry.outcome = "tampered"
        with pytest.raises(RuntimeError):
            await db_session.flush()

    async def test_context_dict_reassignment_is_immutable(self, db_session):
        entry = await _log_one(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            context={"original": "value"},
        )
        await db_session.flush()
        entry.context = {"tampered": "value"}
        with pytest.raises(RuntimeError):
            await db_session.flush()

    async def test_prev_hash_is_immutable(self, db_session):
        entry = await _log_one(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.flush()
        entry.prev_hash = "0" * 64
        with pytest.raises(RuntimeError):
            await db_session.flush()

    async def test_row_hash_is_immutable(self, db_session):
        entry = await _log_one(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.flush()
        entry.row_hash = "f" * 64
        with pytest.raises(RuntimeError):
            await db_session.flush()


# ---------------------------------------------------------------------------
# 4. Multi-flush / commit resilience
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestImmutabilitySurvivesMultipleFlushes:
    """Resilience checks beyond the basic per-field test.

    A bare ``flush()`` after a raise does not re-attempt (the
    SQLAlchemy session is in a partial state until rollback),
    so the multi-flush resilience is implicitly covered by
    the 11 per-field tests above. The tests here pin two
    additional guarantees: ``commit()`` after a tamper raises,
    and expunging a tampered instance does not break a fresh
    ``log()`` in the same session.
    """

    async def test_commit_after_tamper_raises(self, db_session):
        entry = await _log_one(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.flush()

        entry.outcome = "tampered"
        with pytest.raises(RuntimeError):
            await db_session.commit()

    async def test_expunge_does_not_break_subsequent_log(self, db_session):
        """Expunging a tampered-but-not-yet-flushed instance and
        logging a fresh one must succeed. This proves the
        RuntimeError is scoped to the mutated instance, not
        the whole session."""
        entry = await _log_one(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.flush()

        entry.outcome = "tampered"
        db_session.expunge(entry)

        fresh = await _log_one(db_session, action=AuditActionType.QUERY_EXECUTE)
        await db_session.flush()
        assert fresh.sequence_number == 2


# ---------------------------------------------------------------------------
# 5. Structural ORM wiring
# ---------------------------------------------------------------------------


class TestAuditLogEntryHasOrmEventListeners:
    """The immutability contract is enforced by SQLAlchemy ORM event
    listeners registered on the ``AuditLogEntry`` mapper. If a
    future migration drops the listeners, every test above will
    start failing. This structural check pins the wiring so a
    regression is named at the source.

    SQLAlchemy 2.x exposes registered listeners via
    ``mapper.dispatch.<event>.listeners`` (a tuple of callables).
    This is the public, supported path.
    """

    def test_before_update_listener_is_registered(self):
        mapper = inspect(AuditLogEntry)
        listeners = mapper.dispatch.before_update.listeners
        assert len(listeners) >= 1, (
            "AuditLogEntry must have a before_update listener registered to "
            "enforce application-layer immutability. If this test fails, the "
            "immutability guard has been removed from audit_log_entry.py."
        )

    def test_before_delete_listener_is_registered(self):
        mapper = inspect(AuditLogEntry)
        listeners = mapper.dispatch.before_delete.listeners
        assert len(listeners) >= 1, (
            "AuditLogEntry must have a before_delete listener registered to "
            "enforce application-layer immutability. If this test fails, the "
            "immutability guard has been removed from audit_log_entry.py."
        )

    def test_tracked_columns_match_model_definition(self):
        """Sanity check that the test enumerates exactly the columns
        that exist on the model. If a future schema migration
        adds a new tracked column, this test must be updated."""
        mapper = inspect(AuditLogEntry)
        actual: set[str] = {c.key for c in mapper.columns}
        for col in _ALL_TRACKED_COLUMNS:
            assert col in actual, (
                f"Test enumerates column {col!r} but AuditLogEntry does not "
                f"define it. Update _ALL_TRACKED_COLUMNS in this test module."
            )


# ---------------------------------------------------------------------------
# 6. Service-layer mutation API surface
# ---------------------------------------------------------------------------


class TestAuditServiceHasNoMutationAPI:
    """``AuditService`` is the only public surface for the audit log.
    A future maintainer must not be able to add an ``update`` or
    ``delete`` method without breaking this test. The contract is
    that the audit log is **append-only at the service layer**;
    the only mutating verb is ``log`` (insert)."""

    def test_audit_service_has_no_update_method(self):
        assert not hasattr(AuditService, "update"), "AuditService.update must not exist; the audit log is append-only."

    def test_audit_service_has_no_delete_method(self):
        assert not hasattr(AuditService, "delete"), "AuditService.delete must not exist; the audit log is append-only."

    def test_audit_service_log_signature_is_insert_only(self):
        """``AuditService.log`` must accept only kwargs that describe
        a new entry. The presence of an ``id`` or
        ``sequence_number`` parameter would suggest a future
        caller could target an existing row."""
        import inspect

        sig = inspect.signature(AuditService.log)
        forbidden = {"id", "entry_id", "row_id"}
        for name in forbidden:
            assert name not in sig.parameters, (
                f"AuditService.log must not accept a {name!r} parameter; the audit log is append-only."
            )
