# Phase 5 Orchestration Log

## Phase 5 Initialization
- **Status**: TASKS COMPLETE — READY FOR WAVE 17.0 DISPATCH
- **Date**: 2026-05-24
- **Spec**: `specs/005-sso-rbac-row-column-security/spec.md`
- **Plan**: `specs/005-sso-rbac-row-column-security/plan.md`
- **Research**: `specs/005-sso-rbac-row-column-security/research.md`
- **Data Model**: `specs/005-sso-rbac-row-column-security/data-model.md`
- **API Contracts**: `specs/005-sso-rbac-row-column-security/contracts/api-contracts.md`
- **Tasks**: `specs/005-sso-rbac-row-column-security/tasks.md`
- **Prior Phase Status**: Phases 1-4 FROZEN on `main`
- **Branch Context**: `main`

### Locked Scope
- SSO for end users via OIDC and SAML.
- Local password login remains admin-only.
- RBAC with fixed platform permission set.
- Admin-prioritized multi-group role resolution; lowest priority number wins.
- Row filters are validated at save time, parameterized at execution, and fail closed on schema drift.
- Column masks apply before result serialization and surface localized masked-column indicators.
- LLM schema context is role-filtered before prompt construction.
- Evaluator blocks unauthorized table/column references before execution.
- Tamper-evident audit log uses chained hashes with 24-month retention requirement.
- Quotas and hostile input/injection detection remain deferred to Phase 6.

### Wave Structure
| Wave | Tasks | Scope | Owner |
|---|---:|---|---|
| Governance | T-600 | Initialize orchestration log | Opus Orchestrator |
| 17.0 | T-601-T-634 | Foundation contracts, data model, auth architecture | Qwen Backend |
| 17.1 | T-635-T-670 | OIDC/SAML SSO and admin-safe local login | Qwen Backend + Gemini Frontend |
| 17.2 | T-671-T-697 | RBAC roles, group mapping, route/API gates | Qwen Backend + Gemini Frontend |
| 17.3 | T-698-T-732 | Row filters, column masks, LLM schema filtering, evaluator enforcement | Qwen Backend + Gemini Frontend |
| 17.4 | T-733-T-750 | Tamper-evident audit log coverage and verification UI/API | Qwen Backend + Gemini Frontend |
| 17.5 | T-751-T-778 | Arabic/RTL polish, cross-dialect verification, final audit/closeout | Gemini Frontend + Qwen Backend + Opus Orchestrator |

### Dispatch Order
1. Complete T-600 orchestration initialization.
2. Dispatch Wave 17.0 to Qwen Backend Implementer only after T-600 is committed/available.
3. Merge each wave to `main` before dispatching the next wave.
4. Run per-wave gates and append review outcomes here.
5. Phase 5 becomes FROZEN only after final PR merge to `main`, final snapshot, and AGENTS.md status update.

### T-600 Completion
- **Owner**: Opus Orchestrator
- **Status**: COMPLETE
- **Date**: 2026-05-24
- **Evidence**: This orchestration log created with Phase 5 metadata, prior phase status, wave structure, and dispatch order.

---

## Wave 17.0a — Foundation Models

### Dispatch
- **Date**: 2026-05-24
- **Model**: Qwen/Kimi Backend Implementer
- **T-IDs**: T-601 through T-617
- **Branch**: `phase-5/wave-17.0a-foundation-models`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/101

### Review & Merge
- **Date**: 2026-05-24
- **Status**: MERGED
- **Final HEAD**: `5aff092`
- **Tasks Completed**: T-601 through T-617
- **Gates**: Backend unit gate passed; Ruff check passed; Ruff format check passed; CI passed.

### Review Finding Resolved
- **Finding**: `AuditActionType` omitted `policy.schema_mismatch`, required by Phase 5 fail-closed row-filter schema drift plan.
- **Resolution**: Added `POLICY_SCHEMA_MISMATCH = "policy.schema_mismatch"`, updated enum test, data model, and task wording from 21 to 22 audit action types.

### Quirk Captured
- SQLAlchemy 2 `default` / `server_default` do not populate normal ORM instance attributes at `__init__`; tests should inspect column metadata or flush/refresh instead.

### Orchestrator Decision
- **Wave 17.0a status**: COMPLETE — merged to `main`.
- **Next dispatch**: Wave 17.0b, T-618 through T-623, backend only.

---

## Wave 17.0b — Audit Service & Migration

### Dispatch
- **Date**: 2026-05-24
- **Model**: Qwen/Kimi Backend Implementer
- **T-IDs**: T-618 through T-623
- **Branch**: `phase-5/wave-17.0b-audit-migration`
- **PR**: Merged to `main`

### Review & Merge
- **Status**: MERGED
- **Tasks Completed**: T-618 through T-623
- **Gates**: Backend unit gate passed; Ruff check passed; Ruff format check passed; CI passed.

### Quirk Captured
- SQLAlchemy 2 `default` / `server_default` do not populate normal ORM instance attributes at `__init__`; tests should inspect column metadata or flush/refresh instead.

---

## Wave 17.0c — Permission Middleware, Schemas, Session Extension

### Dispatch
- **Date**: 2026-05-24
- **Model**: Qwen/Kimi Backend Implementer
- **T-IDs**: T-624 through T-633
- **Branch**: Merged to `main`

### Review & Merge
- **Status**: MERGED
- **Tasks Completed**: T-624 through T-633
- **Gates**: Backend unit gate passed; Ruff check passed; Ruff format check passed; CI passed.

---

## Wave 17.0d — Test Taxonomy Hardening

### Dispatch
- **Date**: 2026-05-24
- **Model**: Qwen/Kimi Backend Implementer
- **T-IDs**: T-634
- **Branch**: Merged to `main`

### Review & Merge
- **Status**: MERGED
- **Tasks Completed**: T-634
- **Gates**: Backend unit gate passed; Ruff check passed; Ruff format check passed; CI passed.

---

## Wave 17.1a — SSO Service Backend (OIDC/SAML + Role Resolution)

### Dispatch
- **Date**: 2026-05-24
- **Model**: Kimi (opencode) Backend Implementer
- **T-IDs**: T-635 through T-643
- **Branch**: `phase-5/wave-17.1a-sso-service-backend`
- **PR**: https://github.com/RkShanks/QueryCraft/pull/105

### Scope
- OIDC authorization code flow: state/nonce generation, Redis storage, redirect URL, ID token validation (issuer, audience, signature via JWKS, expiry, nonce, replay protection).
- SAML AuthnRequest flow: request ID generation, Redis storage, redirect URL, assertion validation (issuer, audience, signature, timestamps, replay protection).
- Role resolution: SSO group mappings + admin priority ordering (lowest priority number wins), user identity create/update.
- Explicitly NOT included: SSO API endpoints (T-644+), local login restriction, admin SSO CRUD, frontend, Wave 17.2+ RBAC gates.

### Review Findings & Fixes
1. **Fix-1**: OIDC explicit JWKS fetch via `httpx.AsyncClient.get()`, SAML SP/IdP entity separation, provider binding, `BASE_URL` config.
2. **Fix-2**: SAML `wantAssertionsSigned=True`, fail-closed `_get_idp_sso_url`/`_get_idp_entity_id`, removed tautological audience re-check, removed fake `has_signature`.
3. **Fix-3**: Sanitized python3-saml boundary — `process_response()` wrapped in try/except, re-raises `SsoValidationError("SSO assertion validation failed")` from original exception. Added `test_sso_saml_boundary.py` with 6 tests proving settings include `wantAssertionsSigned=True`, SP `entityId` matches provider, and both `process_response()` and `get_errors()` exceptions are sanitized.

### Merge
- **Date**: 2026-05-24
- **Status**: MERGED
- **Final HEAD**: `be572eff95a0ebff058a09d16c37ed113ad38bc4`
- **Tasks Completed**: T-635 through T-643
- **Gates**:
  - Full unit gate: `774 passed, 9 deselected, 1 warning in 12.83s`
  - Focused SAML tests: `36 passed`
  - Focused OIDC tests: `38 passed`
  - Role+provider tests: `15 passed`
  - Ruff check: `All checks passed!`
  - Ruff format: `270 files already formatted`
  - CI: `backend-test` SUCCESS, `frontend-test` SUCCESS

### Security Notes
- `SsoValidationError` wraps all user-facing SSO errors; message never contains raw tokens, certs, UUIDs, hostnames, assertion XML.
- Replay cache uses Redis; TTL = session idle timeout (28800s).
- Clock skew tolerance: `timedelta(seconds=30)` for both OIDC exp and SAML NotBefore/NotOnOrAfter.
- `python3-saml` private API fallback (`_OneLogin_Saml2_Auth__build_request`) documented with comment; wrapped in public-API-first try/except.

### Next Dispatch
- Wave 17.1b: T-644 (replay protection tests), T-645-T-646 (SSO endpoints), T-647-T-648 (local login restriction), T-649-T-651 (admin SSO CRUD), T-652-T-653 (lockout prevention), T-654-T-655 (SSO audit logging), T-656-T-657 (concurrent session limit), T-658 (Wave 17.1 backend gate).

---

## Current Wave Checkpoint — Through Wave 17.1a

### Status
- **Date**: 2026-05-24
- **Phase**: Phase 5 remains IN PROGRESS.
- **Current point**: Wave 17.1a complete and merged; Wave 17.1b not dispatched yet.
- **Merged Phase 5 PRs so far**: #101, #102, #103, #104, #105.
- **Docs PR**: #106 records orchestration progress through this checkpoint.

### Completed Scope Through This Point
- Wave 17.0 foundation is complete through subwaves 17.0a-17.0d:
  - Foundation models and enums.
  - Migration and tamper-evident audit service foundation.
  - Permission dependency, Phase 5 schemas, extended auth/session profile, OpenAPI update.
  - Backend test taxonomy hardening and fast-gate simplification.
- Wave 17.1a backend SSO service slice is complete:
  - OIDC authorization-code initiation and callback validation.
  - Explicit OIDC JWKS fetch and signature validation.
  - SAML AuthnRequest/callback service wrapper with fail-closed metadata behavior.
  - SAML signed-assertion requirement via python3-saml settings.
  - Sanitized python3-saml boundary errors.
  - Provider-bound OIDC state and SAML request replay protection.
  - SSO group to role resolution by priority.
  - UserIdentity create/update and Redis session creation.

### Review Decisions Locked
- OIDC must fetch JWKS explicitly and pass JWKS data, not a URL string, to JWT validation.
- SAML `saml_entity_id` is SP entity ID; IdP issuer is derived from IdP metadata configuration.
- SAML paths fail closed when IdP metadata URL/XML-derived settings are unavailable.
- `SsoValidationError` is the user-facing SSO error boundary; raw tokens, certs, UUIDs, hostnames, assertion XML, and parser/security details stay out of user-facing messages.
- Backend fast gate remains `uv run pytest tests/unit -q -m "not integration"`.

### Remaining Wave 17.1 Work
- T-644: focused replay-protection tests.
- T-645-T-646: SSO auth endpoints and router registration.
- T-647-T-648: local login restriction to admin-only local accounts.
- T-649-T-651: admin SSO provider CRUD and secret masking.
- T-652-T-653: built-in admin lockout prevention tests and implementation.
- T-654-T-655: SSO login/audit events.
- T-656-T-657: concurrent session limit tests and enforcement.
- T-658: Wave 17.1 backend gate.

### Next Dispatch Constraint
- Dispatch Wave 17.1b as a backend-only PR before frontend Wave 17.1 surfaces, because endpoints/admin CRUD/local-login behavior must exist before UI integration.
