# Opus Audit Findings — Wave 17 (Phase 5)

Auditor: Opus 4.6 (independent)
HEAD: `4736179` on `phase-5/wave-17.5b-cross-dialect-security`
Date: 2026-06-07
Scope: PRs #101–#148 (Waves 17.0–17.5b)
Constraint: audit-only — ZERO product code changes

---

## Executive Summary

Phase 5 implements SSO (OIDC + SAML), RBAC with permission gating,
row-level filter injection, column-level masking, tamper-evident audit
log with chained SHA-256, and error sanitization. The implementation is
**solid and production-grade**. Two findings carried forward from the
Gemini audit are confirmed. One new finding identified. No critical
findings.

---

## Findings

### F-001 · HIGH · Audit Retention Unenforced (FR-142)

| Key | Value |
|---|---|
| Loc | `backend/src/app/core/config.py:65` |
| FR | FR-142 (24-month minimum retention) |
| SC | SC-060 |

**Bug**: `AUDIT_RETENTION_MONTHS = 24` declared in config. No background
job, no cron task, no admin endpoint, no migration, no ORM-level
enforcement exists to prune or archive rows older than the configured
window. The table grows without bound.

**Impact**: FR-142 compliance gap. The config value is aspirational
only. No data is ever deleted, so retention is _exceeded_ (not
violated) in a strict sense — but the spec requires an _enforced_
retention policy, not an unbounded append.

**Recommendation**: Implement a scheduled task or admin endpoint in
Phase 6 (already on the roadmap). The current state is a documentation
gap, not a data leak. Severity HIGH because the spec explicitly
requires enforcement.

---

### F-002 · MID · AuditService Central Redaction Incomplete (FR-143)

| Key | Value |
|---|---|
| Loc | `backend/src/app/services/audit_service.py:33-47` |
| FR | FR-143 (no secrets/PII in audit log) |
| SC | SC-061 |

**Bug**: `_SENSITIVE_TOKENS` set missing: `nonce`, `state`, `code`,
`accesstoken`, `idtoken`, `refreshtoken`. These 6 tokens ARE present
in `SsoService._safe_audit_context()` (lines 103-125 of
`sso_service.py`), which pre-redacts before calling `AuditService.log`.

**Impact**: No _active_ leak today — `SsoService` applies defence-in-
depth redaction at call site. But any future direct caller of
`AuditService.log` passing these keys would write plaintext to the
immutable audit log. Mid severity because the defence-in-depth layer
holds.

**Recommendation**: Align `_SENSITIVE_TOKENS` in `audit_service.py`
with the superset in `sso_service.py`. Single-line fix, zero risk.

---

### F-003 · LOW · `LLMUnavailable` Exception Carries Provider Name

| Key | Value |
|---|---|
| Loc | `backend/src/app/core/exceptions.py:46-48` |
| FR | FR-139 (error sanitization) |

**Bug**: `LLMUnavailable.__init__` stores `provider` in `self.provider`
and constructs a message `"LLM provider '{provider}' is unavailable"`.
The query endpoint catches this and returns the constant i18n key
`error.llmUnavailable` (never the message). The exception message is
internal-only (logs, not HTTP responses).

**Impact**: Zero user-facing leak. The provider name reaches structured
logs only. LOW because the exception _could_ be re-raised unwrapped
by a future handler, but the current code is safe.

**Recommendation**: No action required. The HTTP layer is properly
sanitized.

---

## FR Coverage Matrix

| FR | Title | Verdict | Evidence |
|---|---|---|---|
| FR-115 | OIDC authorization code flow | ✅ PASS | `sso_service.py:67-95` — state/nonce in Redis, PKCE-ready |
| FR-116 | OIDC callback validation | ✅ PASS | `sso_service.py:132-256` — issuer/aud/exp/nonce/sig checked |
| FR-117 | SAML AuthnRequest initiation | ✅ PASS | `sso_service.py:354-377` — request_id in Redis, zlib+b64 |
| FR-118 | SAML assertion callback | ✅ PASS | `sso_service.py:471-617` — assertion_id replay protection |
| FR-119 | Role resolution from SSO groups | ✅ PASS | `sso_service.py:713-731` — priority ordering, deterministic |
| FR-120 | Local login restricted to admin | ✅ PASS | `auth_service.py:53-68` — auth_provider+role double gate |
| FR-121 | SSO error redirect sanitized | ✅ PASS | `sso_auth.py:36-63` — `_SSO_ERROR_MAP` → safe codes only |
| FR-122 | Role CRUD with permissions | ✅ PASS | `admin_roles.py:234-303` — full CRUD, permission validation |
| FR-123 | SSO group → role mapping | ✅ PASS | `sso_group_mapping` model + `resolve_role_from_groups` |
| FR-124 | Priority-based role resolution | ✅ PASS | `sso_service.py:727` — `ORDER BY priority ASC, name ASC` |
| FR-125 | Permission enum gating | ✅ PASS | `permissions.py:13-52` — `require_permission` dependency |
| FR-126 | Unmapped user denial | ✅ PASS | `permissions.py:38-43` — empty `role_id` → 403 |
| FR-127 | Concurrent session limit | ✅ PASS | `sso_service.py:817-826` — `MAX_CONCURRENT_SESSIONS_PER_USER` |
| FR-128 | Schema filtering by role | ✅ PASS | `policy_enforcement.py:210-259` — `filter_schema` |
| FR-129 | LLM prompt sees filtered schema | ✅ PASS | `query_service.py:219-246` — `_policy_schema_for_prompt` |
| FR-130 | Role authorization evaluator rule | ✅ PASS | `role_authorization.py:66-460` — full AST walk, star handling |
| FR-131 | Row filter validation & injection | ✅ PASS | `policy_enforcement.py:262-633` — sqlglot AST, 3 dialects |
| FR-132 | Column masking post-execution | ✅ PASS | `policy_enforcement.py:636-756` — `apply_column_masks` |
| FR-133 | Frontend masked column indicator | ✅ PASS | `ColumnMeta.masked` flag propagated to response |
| FR-134 | History isolation by user_id | ✅ PASS | `history.py:1-21` — `WHERE user_id = current_user.id` |
| FR-135 | Built-in role/user protection | ✅ PASS | `role_repository.py:49-78` + `user_repository.py:32-38` |
| FR-136 | Policy test dry-run endpoint | ✅ PASS | `admin_roles.py:598-817` — no LLM, no execution |
| FR-137 | i18n error keys in all responses | ✅ PASS | All HTTPException details carry `message_key` |
| FR-138 | Arabic/RTL parity | ✅ PASS | `en.json` ↔ `ar.json` diff = empty (100% parity) |
| FR-139 | Error sanitization | ✅ PASS | No raw SQL/UUID/host/port/stack in any HTTP response |
| FR-140 | Audit logging for all security events | ✅ PASS | `query_service.py`, `sso_service.py`, `role_service.py` |
| FR-141 | Audit chain verification endpoint | ✅ PASS | `admin_audit.py:109-176` — POST /admin/audit/verify |
| FR-142 | 24-month retention enforcement | ⚠️ PARTIAL | Config declared; no enforcement mechanism (F-001) |
| FR-143 | No secrets/PII in audit log | ⚠️ PARTIAL | Defence-in-depth holds; central tokens incomplete (F-002) |
| FR-144 | Audit chain integrity (SHA-256) | ✅ PASS | `audit_service.py:72-76` — chained hashing, genesis seed |
| FR-145 | Audit immutability | ✅ PASS | `audit_log_entry.py:39-43` — ORM event guard |
| FR-146 | Cross-dialect security parity | ✅ PASS | `_SQLGLOT_DIALECT` maps PG/MySQL/MSSQL; integration tests |

---

## SC Coverage Matrix

| SC | Title | Verdict | Evidence |
|---|---|---|---|
| SC-046 | OIDC replay protection | ✅ PASS | State consumed before token exchange (line 168) |
| SC-047 | SAML assertion replay | ✅ PASS | assertion_id stored in Redis, checked before allow (line 550) |
| SC-048 | Unmapped user → 403 | ✅ PASS | `permissions.py:38-43` role_id emptiness check |
| SC-049 | No cross-user history | ✅ PASS | `history.py` + `AcceptedQueryRepository` — user_id filter |
| SC-050 | Role-auth evaluator blocks unauthorized SQL | ✅ PASS | `RoleAuthorizationRule` — constant reason, no leak |
| SC-051 | Row filter parameterized (no interpolation) | ✅ PASS | `bind_placeholders` → `$N`/`%s`/`?` + params tuple |
| SC-052 | Column mask replaces values | ✅ PASS | `_MASK_TOKEN = "***"`, `ColumnMeta.masked = True` |
| SC-053 | History scoped to current user | ✅ PASS | `WHERE accepted_queries.user_id = :user_id` |
| SC-054 | Built-in role protected from deletion | ✅ PASS | `BuiltinProtectedError` raised, 403 returned |
| SC-055 | Schema drift fails closed | ✅ PASS | `_check_schema_drift` → `PolicySchemaConflictError` |
| SC-056 | Filter validation rejects DML/DDL/subquery/function | ✅ PASS | `_DANGEROUS_TOPLEVEL`, union/intersect/except/subquery/func checks |
| SC-057 | Provider binding prevents state swapping | ✅ PASS | `stored_provider_id != str(provider.id)` → reject |
| SC-058 | Session token never in audit log | ✅ PASS | `auth_service.py:180` — SHA-256 digest with `sha256:` prefix |
| SC-059 | Audit chain starts from GENESIS | ✅ PASS | `audit_service.py:151` — `prev_hash = "GENESIS" if next_seq == 1` |
| SC-060 | Verify endpoint walks full chain | ✅ PASS | `audit_service.py:172-204` — `verify_chain` |
| SC-061 | No secrets in audit context | ⚠️ PARTIAL | SSO pre-redacts; central tokens incomplete (F-002) |
| SC-062 | Errors never expose raw internals | ✅ PASS | All `HTTPException` details use constant i18n keys |

---

## Security Deep-Dive

### SSO Authentication (OIDC + SAML)

**OIDC flow** (`sso_service.py:67-256`):
- State: `secrets.token_urlsafe(32)` — 256-bit entropy
- Nonce: separate `secrets.token_urlsafe(32)` — bound to state in Redis
- Replay: state consumed (Redis DELETE) before token exchange
- Token validation: authlib JWKS fetch + `jwt.decode` + `claims.validate()`
- Claims: issuer, audience (list-aware), expiry (30s clock skew), nonce
- Provider binding: stored `provider_id` checked against callback provider
- Audit failure: session revoked if audit log write fails (no audit-less login)

**SAML flow** (`sso_service.py:354-617`):
- Request ID: `secrets.token_urlsafe(32)` stored in Redis
- Assertion: python3-saml `process_response()` + `wantAssertionsSigned=True`
- Replay: assertion_id stored in Redis after first use; duplicate → reject
- Issuer: validated against IdP entity ID derived from metadata URL
- Timestamps: `not_before`, `not_on_or_after` with 30s clock skew
- Certificate: AES-256-GCM encrypted at rest (`encryption.py`)
- Error sanitization: raw python3-saml exceptions caught and re-raised as
  `SsoValidationError("SSO assertion validation failed")`

**Verdict**: Both flows are correctly implemented with defence-in-depth.

### RBAC Enforcement

**Permission middleware** (`permissions.py:13-52`):
- `require_permission(*perms)` returns async dependency
- 401 if no session; 403 if `role_id` empty/missing OR no matching permission
- Uses set intersection: `user_perms & required`

**Role resolution** (`sso_service.py:713-731`):
- Priority-based: `ORDER BY priority ASC, name ASC` (deterministic)
- Returns `None` if no group maps → `SsoValidationError("SSO user has no assigned role")`

**Built-in protection** (`role_repository.py:49-78`, `user_repository.py:32-38`):
- `is_builtin=True` → `BuiltinProtectedError` on delete
- Core fields (`name`, `permissions`, `is_builtin`, `priority`) protected on update

### Row-Level Security

**Validation** (`policy_enforcement.py:262-383`):
- Comments rejected outside strings (custom lexer, not sqlglot)
- Dangerous AST nodes: INSERT/UPDATE/DELETE/MERGE/CREATE/DROP/ALTER/TRUNCATE/COMMAND/COPY/SET
- Set operations: UNION/INTERSECT/EXCEPT → reject
- Subqueries: nested SELECT → reject
- Function calls: all `exp.Func` except boolean/comparison/arithmetic operators
- Column existence: validated against target table schema
- Table qualifier: must match target table (prevents cross-table reference)
- Placeholders: `{user.email}`, `{user.subject_id}`, `{user.role}` only

**Binding** (`policy_enforcement.py:385-467`):
- Per-dialect: `$N` (postgres), `%s` (mysql), `?` (mssql)
- Values in `params` tuple — never string-interpolated
- Missing/None user context values → fail closed

**Injection** (`policy_enforcement.py:470-633`):
- Schema drift guard: every column re-checked at injection time
- AST AND-conjunction via sqlglot
- Post-processing: driver-style placeholder renumbering
- String-literal aware replacement (PR #126 fix)

### Column-Level Masking

**`apply_column_masks`** (`policy_enforcement.py:636-756`):
- Fail-closed: malformed config → `ValueError("column_mask_config_invalid")`
- Case-insensitive matching
- Returns NEW QueryResult (input never mutated)
- `ColumnMeta.masked = True` for masked columns
- `_MASK_TOKEN = "***"` — dialect-agnostic

### Tamper-Evident Audit Log

**Chaining** (`audit_service.py:72-76`):
- `_compute_row_hash`: canonical JSON + prev_hash → SHA-256
- Genesis: `prev_hash = "GENESIS"` for `sequence_number = 1`
- Row-level lock: `FOR UPDATE` on sequence number query

**Immutability** (`audit_log_entry.py:39-43`):
- ORM event listener: `before_update` and `before_delete` → `RuntimeError`

**Verification** (`audit_service.py:172-204`):
- Full chain walk: reconstructs payload → recomputes hash → compares
- Returns `VerificationResult(verified, entries_checked, first_break_at)`

**Redaction** (`audit_service.py:50-60`):
- Recursive dict/list redaction
- 12 sensitive tokens (password, secret, token, apikey, credential,
  certificate, privatekey, assertion, samlresponse, authorization,
  encryptionkey, bearer, jwt)
- Missing 6 tokens from SSO layer (F-002)

### Error Sanitization

Every `HTTPException` in the API layer uses constant `message_key` values.
No `str(exc)` is ever passed to the HTTP response — the pattern in
`admin_roles.py` uses `str(exc)` only for internal pattern matching
(`"duplicate_name" in msg`) and re-raises with constant detail dicts.
All exception chains use `from None` to suppress chained exception context.

**Verified zero-leak surfaces**:
- SSO callbacks → redirect with safe error code
- Query flow → constant i18n keys
- Audit endpoints → sanitized 500 catch-all
- Role CRUD → constant error codes
- History → constant error codes

### i18n / Arabic Parity

`en.json` ↔ `ar.json` diff: **empty** (100% key parity confirmed).
All Phase 5 error keys present in both locales.

---

## Test Coverage

36 test files covering Phase 5 security:
- SSO: 14 test files (OIDC flow, SAML flow, callbacks, errors, boundary, JWKS, provider binding, issuer, signed assertions)
- Policy: 3 test files (cross-dialect, query flow, test endpoint)
- Audit: 9 test files (chain verification, endpoints, event coverage, immutability, redaction, model, service)
- RBAC: 6 test files (role endpoints, model, resolution, connection policy, audit logging)
- Integration: 1 file (cross-dialect policy)
- Factory wiring: 1 file (T-712 provider)

---

## Gemini Finding Cross-Reference

| Gemini Finding | Opus Verdict |
|---|---|
| HIGH: Audit retention unenforced (FR-142) | **CONFIRMED** → F-001 |
| MID: AuditService missing OIDC redaction tokens (FR-143) | **CONFIRMED** → F-002 |

Both findings independently verified. No disagreement with Gemini audit.

---

## Conclusion

Phase 5 security implementation is **production-ready** with 2 known
deferred items (F-001, F-002) that do not represent active data leaks.

- **0 Critical findings**
- **1 High finding** (F-001: retention enforcement — deferred to Phase 6)
- **1 Mid finding** (F-002: central redaction tokens — single-line fix)
- **1 Low finding** (F-003: exception message in logs — no user-facing leak)

**Gate recommendation**: PASS for Phase 5 close. F-001 deferred to Phase 6
(Quotas/Hardening). F-002 should be fixed before Phase 6 dispatch as a
`chore/audit-redaction-alignment` PR.

## Disposition (post-Wave 17.5c hardening)

PR: `phase-5/wave-17.5c-audit-findings-hardening`

| Finding | Severity | Disposition | Implementation summary |
|---|---|---|---|
| F-001 · Audit Retention Unenforced (FR-142) | HIGH | **FIXED** | `AuditService.purge_expired_entries(session, retention_months=None)` with `compute_retention_cutoff(retention_months, now=None)` helper. Default `retention_months` from `Settings.AUDIT_RETENTION_MONTHS` (24). No internal scheduler invented — operators invoke from external cron / k8s CronJob. Post-prune chain verification behavior is documented in the docstring and pinned by tests: `verify_chain` will honestly report a break at the first surviving row because that row's `prev_hash` references a now-deleted row's `row_hash`. The retained window is internally consistent but the on-disk chain no longer starts at `GENESIS`; the chain is not silently rewritten to lie. |
| F-002 · AuditService Central Redaction Incomplete (FR-143) | MID | **FIXED** | `_SENSITIVE_TOKENS` in `app/services/audit_service.py` extended with `nonce`, `state`, `code`, `accesstoken`, `idtoken`, `refreshtoken`. The set now mirrors `SsoService._safe_audit_context` (sso_service.py) verbatim. `access_token` / `id_token` / `refresh_token` (snake_case) were already substring-matched by the `token` token; added explicitly to make the security boundary self-documenting. The structural sweep `_FORBIDDEN_KEY_TOKENS` in `test_audit_redaction_comprehensive.py` is updated in lock-step. |
| F-003 · `LLMUnavailable` Carries Provider Name | LOW | **NOT FIXED** (intentional) | Per dispatch: "Do not fix unless trivial and no scope creep." Zero user-facing leak (sanitized at the HTTP layer; i18n key only). No code change. |

### Operational note for F-001

Operators must schedule `AuditService.purge_expired_entries(session)` (or pass an explicit `retention_months`) on a recurring interval. Suggested cadence is **monthly** (so that the worst-case retention drift is one month). The cut-off is computed with `dateutil.relativedelta(months=retention_months)`, so calendar arithmetic is correct across leap years and month-end boundaries.
