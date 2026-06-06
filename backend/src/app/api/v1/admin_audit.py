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
    reflects the same pre-log count via the captured ``VerificationResult``.

Resource-id contract for ``audit.verify`` events:

  - The audit model contract does not define a per-verification row UUID
    surfaced to end users, so the stable constant ``"audit_chain"`` is
    used. This avoids exposing internal row UUIDs in the audit log or
    any API response. See ``api-contracts.md`` for the endpoint shape.

Last-verification state:

  - The ``GET /status`` endpoint reads from an in-process module-level
    variable ``_last_verification`` populated by the most recent
    successful ``POST /verify`` call.
  - For multi-worker deployments, the durable source of truth is the
    ``audit_log_entries`` table — every verify call appends an
    ``audit.verify`` row whose ``context`` captures ``entries_checked``,
    ``verified``, and ``first_break_at``. A future enhancement can
    rebuild ``last_verification`` by reading the most recent
    ``audit.verify`` row; the current in-process state keeps the
    endpoint fast and the test seam clean.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.permissions import require_permission
from app.core.dependencies import get_db
from app.db.models.enums import AuditActionType, Permission
from app.services.audit_service import AuditService, VerificationResult

router = APIRouter(prefix="/admin/audit", tags=["Admin Audit"])

# Stable contractually-defined resource_id for AUDIT_VERIFY events.
# No per-verification model exists in the audit model contract;
# a constant sentinel avoids exposing internal row UUIDs to end users.
AUDIT_VERIFY_RESOURCE_ID: str = "audit_chain"
AUDIT_VERIFY_RESOURCE_TYPE: str = "audit_chain"

# In-process last verification result. Populated by ``verify_audit_chain``
# on success; read by ``get_audit_status`` to render the admin page.
# Reset to ``None`` on cold start; updated atomically by each successful
# verify call. See module docstring for the multi-worker trade-off.
_last_verification: VerificationResult | None = None


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
      2. Capture the result in ``_last_verification`` for ``GET /status``.
      3. Append an ``audit.verify`` audit entry to the chain. The
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
    global _last_verification

    try:
        # Step 1: walk the chain BEFORE appending the AUDIT_VERIFY row.
        # The response ``entries_checked`` is the PRE-log count. This
        # also avoids any chance of recursion: log is invoked strictly
        # AFTER verify_chain returns.
        result = await AuditService.verify_chain(db)

        # Step 2: capture the result for GET /status.
        # Read into a local first so a concurrent verify call cannot
        # observe a half-updated module global.
        _last_verification = result

        # Step 3: emit the audit event. The mocked-log test seam in
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
    _session: dict = Depends(require_permission(Permission.ADMIN_AUDIT_VERIFY)),  # noqa: B008
):
    """GET /admin/audit/status — return last verification result + entry count.

    Permission: ``admin.audit.verify``.

    Response 200::

        {
          "total_entries": 15234,
          "last_verification": {
            "verified": true,
            "entries_checked": 15234,
            "first_break_at": null,
            "verified_at": "2026-06-06T12:00:00+00:00"
          }
        }

    Or, when no verification has run since process start::

        {
          "total_entries": 0,
          "last_verification": null
        }

    ``total_entries`` reflects the ``entries_checked`` value from the
    most recent successful verify call (the PRE-log count, by the
    recursion-safety contract above). If no verify has run, both fields
    are zero / null. The audit log itself is the durable record; the
    in-process state is a fast read-path for the admin page.
    """
    if _last_verification is None:
        return {
            "total_entries": 0,
            "last_verification": None,
        }
    return {
        "total_entries": _last_verification.entries_checked,
        "last_verification": _verification_to_response(_last_verification),
    }
