# Gemini Audit Findings - Wave 17

## Scope
- Phase 5 Wave 17.0-17.5b PRs.
- Target: SSO, RBAC, Row/Column Security, Tamper-Evident Audit Logs.

## Findings

### 1. HIGH: Audit Retention Unenforced (FR-142)
- Loc: `backend/src/app/core/config.py`
- Bug: `AUDIT_RETENTION_MONTHS=24` exists in config. No background task/cron/endpoint to delete rows older than 24mo.
- Impact: DB grows indefinitely. FR-142 compliance failure.

### 2. MID: AuditService Missing OIDC Redaction Tokens (FR-143)
- Loc: `backend/src/app/services/audit_service.py` (`_SENSITIVE_TOKENS`)
- Bug: Missing `nonce`, `state`, `code`, `accesstoken`, `idtoken`, `refreshtoken`.
- Impact: `SsoService` pre-redacts these, so no active leak. But central `AuditService` incomplete. Future direct logging of these terms leaks to immutable audit log.

## Verification Summary
- **SSO (FR-115–121)**: Verified. OIDC/SAML flows, fallback lockout, session limit working.
- **RBAC (FR-122–127)**: Verified. Gates active. Unmapped user denial working. Built-in roles protected.
- **Policy (FR-128–136)**: Verified. Row filters (AST injection), column masks, schema filtering, Evaluator auth verified. Schema drift fails closed with sanitized error.
- **Audit (FR-140–144)**: Verified. Chained hashing, immutability, `/admin/audit/verify` working.
- **Sanitization (FR-139, 143)**: Verified. Errors sanitized. No raw UUIDs, SQL, secrets, hostnames leaked in UI/errors.

## Status
- Security validation complete.
- Recommend block merge until High/Mid findings addressed or deferred to Phase 6.

## Disposition (post-Wave 17.5c hardening)

PR: `phase-5/wave-17.5c-audit-findings-hardening`

| Finding | Severity | Disposition |
|---|---|---|
| 1. Audit Retention Unenforced (FR-142) | HIGH | **FIXED** — `AuditService.purge_expired_entries(retention_months)` + `compute_retention_cutoff()` with dateutil-based calendar arithmetic. No internal scheduler shipped (operations team invokes from external cron / k8s CronJob). Post-prune chain verification behavior is documented in the docstring and tested. |
| 2. AuditService Missing OIDC Redaction Tokens (FR-143) | MID | **FIXED** — `_SENSITIVE_TOKENS` now includes `nonce`, `state`, `code`, `accesstoken`, `idtoken`, `refreshtoken`. The set mirrors `SsoService._safe_audit_context` verbatim so the two layers cannot drift. `access_token` / `id_token` / `refresh_token` (snake_case) were already substring-matched by the `token` token; added explicitly to make the security boundary self-documenting. The structural sweep in `test_audit_redaction_comprehensive.py` is updated in lock-step. |
