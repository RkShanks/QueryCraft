"""Admin audit endpoints (T-738).

POST /admin/audit/verify  — trigger audit chain integrity verification
GET  /admin/audit/status   — return last verification result + entry count

Per FR-141, FR-144, S-008, SC-060:

  - S-008 chain recovery: verification walks the chain from genesis and
    reports the ``sequence_number`` of the first mismatch (``first_break_at``).
    No auto-repair. Append continues after a break — see ``AuditService.log``
    which assigns ``next_seq = (last_seq or 0) + 1`` and never re-validates
    the prior chain link. Admin decides recovery action.
  - The verification result itself is recorded as an ``audit.verify``
    audit event after the chain is walked.
  - No raw SQL, host/port, credentials, tokens, SAML/XML/certs, or stack
    traces appear in any response or audit context.

AUDIT_VERIFY emission recursion-safety (defence in depth):

  - ``AuditService.log()`` does NOT call ``AuditService.verify_chain()``
    internally. This is verified statically by
    ``TestVerifyNoInfiniteRecursion.test_audit_service_log_does_not_call_verify_chain``.
  - The verify endpoint runs ``verify_chain`` FIRST, captures the result,
    THEN calls ``AuditService.log(..., action=AUDIT_VERIFY)`` ONCE.
  - The response ``entries_checked`` reflects the chain size at the moment
    of verification (PRE-log). The audit.verify row appended by the same
    call is NOT counted in the same response. A subsequent ``GET /status``
    reflects the durable post-log count (see below).

Resource-id contract for ``audit.verify`` events:

  - The audit model contract does not define a per-verification row UUID
    surfaced to end users, so the stable constant ``"audit_chain"`` is
    used. This avoids exposing internal row UUIDs in the audit log or
    any API response. See ``api-contracts.md`` for the endpoint shape.

``GET /status`` source of truth (durable, DB-derived):

  - ``total_entries`` is the actual ``SELECT COUNT(*) FROM
    audit_log_entries`` result. The count INCLUDES any
    ``audit.verify`` rows that have been appended. This is
    process-restart safe and worker-agnostic.
  - ``last_verification`` is reconstructed from the most recent
    ``audit.verify`` row in ``audit_log_entries`` (ordered by
    ``sequence_number DESC LIMIT 1``). The reconstructed block
    carries ``verified``, ``entries_checked``, ``first_break_at``
    from the row's ``context`` JSONB column, and ``verified_at``
    from the row's ``timestamp``.
  - No in-process module-level cache. The status endpoint is a
    pure read of the durable table. A process restart does not
    lose state.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status  # noqa: F401
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.permissions import require_permission
from app.api.v1.phase6_permissions import require_phase6_admin_permission
from app.core.config import get_settings
from app.core.dependencies import get_db
from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType, Permission
from app.schemas.audit_search import AuditSearchParams
from app.services.audit_search_service import AuditSearchService
from app.services.audit_service import AuditService, VerificationResult

router = APIRouter(prefix="/admin/audit", tags=["Admin Audit"])

# Stable contractually-defined resource_id for AUDIT_VERIFY events.
# No per-verification model exists in the audit model contract;
# a constant sentinel avoids exposing internal row UUIDs to end users.
AUDIT_VERIFY_RESOURCE_ID: str = "audit_chain"
AUDIT_VERIFY_RESOURCE_TYPE: str = "audit_chain"


def _verification_to_response(result: VerificationResult) -> dict[str, Any]:
    """Convert ``VerificationResult`` to the API response shape.

    The shape matches ``AuditVerifyResponse`` defined in
    ``app/schemas/audit.py`` (T-628). The ``last_verification`` block in
    ``GET /status`` reuses the same shape; it carries ``first_break_at``
    for both verified and broken chain states.
    """
    return {
        "verified": result.verified,
        "entries_checked": result.entries_checked,
        "first_break_at": result.first_break_at,
        "verified_at": result.verified_at.isoformat(),
    }


def _row_to_last_verification(row: AuditLogEntry) -> dict[str, Any]:
    """Reconstruct ``last_verification`` from a persisted ``audit.verify`` row.

    The ``context`` JSONB column carries ``verified`` (bool),
    ``entries_checked`` (int), and ``first_break_at`` (int | None).
    ``verified_at`` is the row's persisted ``timestamp``.
    """
    ctx: dict[str, Any] = dict(row.context or {})
    return {
        "verified": bool(ctx.get("verified", False)),
        "entries_checked": int(ctx.get("entries_checked", 0)),
        "first_break_at": ctx.get("first_break_at"),
        "verified_at": row.timestamp.isoformat(),
    }


@router.post("/verify")
async def verify_audit_chain(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _session: dict = Depends(require_permission(Permission.ADMIN_AUDIT_VERIFY)),  # noqa: B008
):
    """POST /admin/audit/verify — walk the audit chain and emit AUDIT_VERIFY.

    Permission: ``admin.audit.verify``.

    Behaviour:
      1. Walk the chain via ``AuditService.verify_chain`` (PRE-log count).
      2. Append an ``audit.verify`` audit entry to the chain. The
         ``outcome`` is ``"success"`` when the chain is intact and
         ``"broken"`` when ``first_break_at`` is not None. The
         ``context`` carries only ``verified`` (bool), ``entries_checked``
         (int), and ``first_break_at`` (int | None) — no raw chain rows,
         no SQL, no schema internals, no driver errors.

    S-008 chain recovery:
      - The endpoint never mutates or rewrites chain rows. No auto-repair.
      - On a broken chain, ``first_break_at`` carries the
        ``sequence_number`` of the first mismatch; admin decides recovery.
      - After a break, the next ``AuditService.log`` call appends with
        ``next_seq = (last_seq or 0) + 1``. The chain restarts from the
        last row's ``row_hash`` regardless of the break.

    Response 200: ``AuditVerifyResponse`` shape
    (``verified``, ``entries_checked``, ``first_break_at``, ``verified_at``).
    """
    try:
        # Step 1: walk the chain BEFORE appending the AUDIT_VERIFY row.
        # The response ``entries_checked`` is the PRE-log count. This
        # also avoids any chance of recursion: log is invoked strictly
        # AFTER verify_chain returns.
        result = await AuditService.verify_chain(db)

        # Step 2: emit the audit event. The mocked-log test seam in
        # test_audit_endpoints.py short-circuits this in HTTP-level tests.
        actor_identity = (_session or {}).get("username") if _session else None
        outcome = "success" if result.verified else "broken"
        await AuditService.log(
            db,
            action=AuditActionType.AUDIT_VERIFY,
            actor_identity=actor_identity,
            resource_type=AUDIT_VERIFY_RESOURCE_TYPE,
            resource_id=AUDIT_VERIFY_RESOURCE_ID,
            outcome=outcome,
            context={
                "verified": result.verified,
                "entries_checked": result.entries_checked,
                "first_break_at": result.first_break_at,
            },
        )

        await db.commit()
        return _verification_to_response(result)
    except HTTPException:
        raise
    except Exception:
        # Defence in depth: any internal failure surfaces as a
        # sanitized 500 with constant i18n key. No host/port,
        # credential, token, driver name, stack trace, or SQL
        # fragment is echoed.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None


@router.get("/status")
async def get_audit_status(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _session: dict = Depends(require_permission(Permission.ADMIN_AUDIT_VERIFY)),  # noqa: B008
):
    """GET /admin/audit/status — return durable last verification + entry count.

    Permission: ``admin.audit.verify``.

    Both ``total_entries`` and ``last_verification`` are read from the
    ``audit_log_entries`` table on every request. The endpoint holds
    no in-process state and survives process restarts.

    Response 200::

        {
          "total_entries": 15235,
          "last_verification": {
            "verified": true,
            "entries_checked": 15234,
            "first_break_at": null,
            "verified_at": "2026-06-06T12:00:00+00:00"
          }
        }

    - ``total_entries`` is the actual durable row count in
      ``audit_log_entries`` (the count INCLUDES any persisted
      ``audit.verify`` rows). This is process-restart safe.
    - ``last_verification`` is reconstructed from the most recent
      ``audit.verify`` row. ``entries_checked`` here reflects the
      PRE-log count captured at verify time (it is the count the
      verify endpoint itself returned, not the post-log count).
      If no verify has ever been performed, ``last_verification``
      is ``null``.

    Or, when the audit log is empty::

        {
          "total_entries": 0,
          "last_verification": null
        }

    Or, when the audit log has rows but no verify has been performed::

        {
          "total_entries": 42,
          "last_verification": null
        }
    """
    # 1. Actual durable row count (process-restart safe, worker-agnostic).
    count_result = await db.execute(select(func.count()).select_from(AuditLogEntry))
    total_entries = int(count_result.scalar_one())

    # 2. Reconstruct last_verification from the most recent audit.verify
    #    row. Filter on the canonical string value of the enum (matches
    #    AuditService.log which stores ``str(AuditActionType.AUDIT_VERIFY)``).
    latest_result = await db.execute(
        select(AuditLogEntry)
        .where(AuditLogEntry.action_type == str(AuditActionType.AUDIT_VERIFY))
        .order_by(AuditLogEntry.sequence_number.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()

    last_verification: dict[str, Any] | None = _row_to_last_verification(latest) if latest is not None else None

    return {
        "total_entries": total_entries,
        "last_verification": last_verification,
    }


@router.get("/entries")
async def search_audit_entries(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _session: dict = Depends(require_phase6_admin_permission(Permission.ADMIN_AUDIT_VERIFY)),  # noqa: B008
    action_type: str | None = Query(default=None),
    actor_identity: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    """GET /admin/audit/entries — filtered, paginated audit log search.

    Permission: ``admin.audit.verify`` (existing Phase 5 permission).

    Behaviour:
      1. Parse filter params from query string.
      2. Enforce retention window server-side (entries older than
         ``AUDIT_RETENTION_MONTHS`` are excluded before pagination).
      3. Return ``AuditSearchResponse`` with paginated entries.
      4. Emit ``AUDIT_SEARCH`` audit event whose context contains ONLY:
         - sanitized filter summary (param names + values, no result content)
         - pagination metadata (page, page_size)
         Never log returned entry values in the audit context.

    Response shape: ``AuditSearchResponse``
    (``entries`` list + ``pagination`` metadata).
    """
    try:
        # Parse dates if provided
        from datetime import datetime

        parsed_start = None
        parsed_end = None
        if start_date:
            try:
                parsed_start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "invalid_date", "message_key": "error.invalid_date", "field": "start_date"},
                ) from None
        if end_date:
            try:
                parsed_end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "invalid_date", "message_key": "error.invalid_date", "field": "end_date"},
                ) from None

        params = AuditSearchParams(
            start_date=parsed_start,
            end_date=parsed_end,
            action_type=action_type,
            actor_identity=actor_identity,
            outcome=outcome,
            resource_type=resource_type,
            page=page,
            page_size=page_size,
        )

        settings = get_settings()
        retention_months = settings.AUDIT_RETENTION_MONTHS

        result = await AuditSearchService.search(db, params, retention_months)

        # Build sanitized filter summary — param names + values only.
        # Never include returned entry content.
        filter_summary: dict[str, Any] = {}
        if action_type is not None:
            filter_summary["action_type"] = action_type
        if actor_identity is not None:
            filter_summary["actor_identity"] = actor_identity
        if outcome is not None:
            filter_summary["outcome"] = outcome
        if resource_type is not None:
            filter_summary["resource_type"] = resource_type
        if start_date is not None:
            filter_summary["start_date"] = start_date
        if end_date is not None:
            filter_summary["end_date"] = end_date

        actor_identity_val = (_session or {}).get("username") if _session else None

        # Emit AUDIT_SEARCH — context: filter summary + pagination metadata only.
        # Never include returned entry values.
        await AuditService.log(
            db,
            action=AuditActionType.AUDIT_SEARCH,
            actor_identity=actor_identity_val,
            resource_type="audit_log",
            resource_id=None,
            outcome="success",
            context={
                "filters": filter_summary,
                "page": page,
                "page_size": page_size,
            },
        )

        await db.commit()
        return result

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None
