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

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, status  # noqa: F401
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.permissions import require_permission
from app.api.v1.phase6_permissions import require_phase6_admin_permission
from app.core.config import get_settings
from app.core.dependencies import get_db, get_redis
from app.core.exceptions import QuotaExceededError, QuotaUnavailableError
from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType, Permission
from app.repositories.quota_repository import QuotaRepository
from app.schemas.audit_search import AuditExportRequest, AuditSearchParams
from app.services.audit_export_service import AuditExportService, ExportLimitExceededError, redact_audit_export_value
from app.services.audit_search_service import AuditSearchService
from app.services.audit_service import AuditService, VerificationResult
from app.services.quota_service import QuotaService

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


async def _get_latest_purge_marker(db: AsyncSession) -> AuditLogEntry | None:
    """Return the most recent ``audit.purge`` marker row, or None.

    Extracted as a module-level coroutine so unit tests can patch it
    without requiring a live database.
    """
    result = await db.execute(
        select(AuditLogEntry)
        .where(AuditLogEntry.action_type == str(AuditActionType.AUDIT_PURGE))
        .order_by(AuditLogEntry.sequence_number.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.get("/retention")
async def get_audit_retention(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _session: dict = Depends(require_permission(Permission.ADMIN_AUDIT_VERIFY)),  # noqa: B008
):
    """GET /admin/audit/retention — return retention policy and last purge summary.

    Permission: ``admin.audit.verify``.

    Response 200::

        {
          "retention_months": 24,
          "last_purge_at": "2026-06-01T03:00:00+00:00",  # or null
          "purged_count": 1500                            # or null
        }

    Fields:
      - ``retention_months``: the configured minimum retention window from
        ``Settings.AUDIT_RETENTION_MONTHS`` (FR-142).
      - ``last_purge_at``: ISO-8601 timestamp of the most recent
        ``audit.purge`` marker row, or ``null`` when no purge has run.
      - ``purged_count``: the ``purged_count`` value stored in the most
        recent ``audit.purge`` marker context, or ``null`` when no purge
        has run.

    Scheduler timing (e.g. next_purge_at, cron schedule) is deliberately
    excluded — it is an external operational concern, not surfaced here.
    """
    settings = get_settings()
    retention_months: int = settings.AUDIT_RETENTION_MONTHS

    latest_purge = await _get_latest_purge_marker(db)

    last_purge_at: str | None = None
    purged_count: int | None = None
    if latest_purge is not None:
        last_purge_at = latest_purge.timestamp.isoformat()
        ctx: dict[str, Any] = dict(latest_purge.context or {})
        purged_count = ctx.get("purged_count")

    return {
        "retention_months": retention_months,
        "last_purge_at": last_purge_at,
        "purged_count": purged_count,
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

        safe_filter_summary = redact_audit_export_value(filter_summary)

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
                "filters": safe_filter_summary,
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


@router.post("/export")
async def export_audit_entries(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
    _session: dict = Depends(require_phase6_admin_permission(Permission.ADMIN_AUDIT_VERIFY)),  # noqa: B008
    export_req: AuditExportRequest = Body(...),  # noqa: B008
):
    """POST /admin/audit/export — export filtered audit entries as CSV or JSON.

    Permission: ``admin.audit.verify`` (existing Phase 5 permission).

    Behaviour:
      1. Check daily export quota via QuotaService.check_and_increment(user_id, role_id, "exports").
         - QuotaExceededError → 429 with message_key.
         - QuotaUnavailableError → 503 with message_key (fail-closed).
      2. Parse AuditExportRequest from typed FastAPI body param (Pydantic-validated — 422 on bad input).
      3. Query entries via AuditSearchService (enforces retention window).
      4. If filtered count > 50,000 → 422 with message_key.
      5. Serialize via AuditExportService (CSV or JSON with redaction + integrity metadata).
      6. Emit AUDIT_EXPORT audit event with only filter_summary and record_count.
         Never include exported entry values in the context.
      7. Return file response with correct Content-Type and Content-Disposition headers.

    Security constraints:
      - No exported entry values in AUDIT_EXPORT context.
      - No stack traces, raw SQL, driver errors, or secrets in any response.
    """
    try:
        # ── Step 1: Quota check (fail-closed) ──────────────────────────────
        user_id_str = _session.get("user_id", "")
        role_id_str = _session.get("role_id", "")
        try:
            user_uuid = uuid.UUID(user_id_str) if user_id_str else uuid.uuid4()
            role_uuid = uuid.UUID(role_id_str) if role_id_str else uuid.uuid4()
        except ValueError:
            user_uuid = uuid.uuid4()
            role_uuid = uuid.uuid4()

        quota_repo = QuotaRepository(db)
        quota_service = QuotaService(redis=redis, quota_repo=quota_repo)
        try:
            await quota_service.check_and_increment(user_uuid, role_uuid, "exports")
        except QuotaExceededError as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"message_key": "error.quota_exceeded", "reset_at": exc.reset_at},
            ) from exc
        except QuotaUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"message_key": "error.service_unavailable"},
            ) from exc

        # ── Step 2: export_req already parsed by FastAPI (typed body param) ─
        # Pydantic validation errors surface as 422 — no manual request.json() needed.

        # ── Steps 3+4: Count + fetch via dedicated export method ────────────
        # get_all_entries_for_export() reuses the same retention-cutoff and ORM
        # filter logic as search() but issues a single uncapped SELECT LIMIT
        # 50_000, bypassing AuditSearchParams.page_size which is capped at 100.
        # It returns (total_count, entries) in one round-trip.
        settings = get_settings()
        retention_months = settings.AUDIT_RETENTION_MONTHS

        total_count, entries = await AuditSearchService.get_all_entries_for_export(
            db,
            retention_months,
            action_type=export_req.action_type,
            actor_identity=export_req.actor_identity,
            outcome=export_req.outcome,
            resource_type=export_req.resource_type,
            start_date=export_req.start_date,
            end_date=export_req.end_date,
        )

        # ── Step 4: Enforce 50k limit ───────────────────────────────────────
        if total_count > 50_000:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message_key": "error.export_limit_exceeded"},
            )

        # ── Step 5: Serialize via AuditExportService ────────────────────────
        actor_identity_val = _session.get("username") or _session.get("user_id") or ""
        export_timestamp = datetime.now(UTC).isoformat()

        # Build sanitized filter summary — param names + values only (no entry content).
        filter_summary: dict[str, Any] = {}
        if export_req.action_type is not None:
            filter_summary["action_type"] = export_req.action_type
        if export_req.actor_identity is not None:
            filter_summary["actor_identity"] = export_req.actor_identity
        if export_req.outcome is not None:
            filter_summary["outcome"] = export_req.outcome
        if export_req.resource_type is not None:
            filter_summary["resource_type"] = export_req.resource_type
        if export_req.start_date is not None:
            filter_summary["start_date"] = export_req.start_date.isoformat()
        if export_req.end_date is not None:
            filter_summary["end_date"] = export_req.end_date.isoformat()
        filter_summary["format"] = export_req.format
        safe_filter_summary = redact_audit_export_value(filter_summary)

        metadata = {
            "export_actor": actor_identity_val,
            "export_timestamp": export_timestamp,
            "filter_summary": str(safe_filter_summary),
            "record_count": len(entries),
        }

        try:
            if export_req.format == "csv":
                payload = AuditExportService.export_csv(entries, metadata)
            else:
                payload = AuditExportService.export_json(entries, metadata)
        except ExportLimitExceededError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message_key": "error.export_limit_exceeded"},
            ) from None

        # ── Step 6: Emit AUDIT_EXPORT event ────────────────────────────────
        # Context: ONLY filter_summary and record_count — never exported entry values.
        await AuditService.log(
            db,
            action=AuditActionType.AUDIT_EXPORT,
            actor_identity=actor_identity_val,
            resource_type="audit_log",
            resource_id=None,
            outcome="success",
            context={
                "filter_summary": safe_filter_summary,
                "record_count": len(entries),
            },
        )
        await db.commit()

        # ── Step 7: Return file response ────────────────────────────────────
        filename_ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        if export_req.format == "csv":
            return Response(
                content=payload,
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="audit_export_{filename_ts}.csv"',
                },
            )
        else:
            return Response(
                content=payload,
                media_type="application/json; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="audit_export_{filename_ts}.json"',
                },
            )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None
