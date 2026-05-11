# Wave 6 (FINAL Phase 1 wave) — US-5 + US-6 + final Polish

Drafted by Kimi K2.6 in Chunk 6.1.
Constitution version: v1.1.1
main HEAD at plan time: `94394be`
Prerequisite waves shipped: 2, 3, 4, 5 (US-1 to US-4 done).

---

## 1. Scope

### In-scope user stories
| US | Priority | FR coverage | SC coverage | Open tasks |
|---|---|---|---|---|
| US-5 | P2 | FR-009, FR-026 | SC-008 | T-174, T-176, T-177, T-178 |
| US-6 | P3 | FR-024, FR-025 | SC-009, SC-010 | T-179, T-180, T-181, T-182, T-183, T-184, T-185, T-186 |

**Note on T-175**: `backend/tests/unit/llm/test_factory.py` (T-085, shipped in Wave 2) already tests unknown-provider rejection via `test_unknown_provider_raises`. T-175 is treated as a false-negative and marked `[x]` in tasks.md.

### Polish rolled into Wave 6
| Task | Why | Effort | Chunk |
|---|---|---|---|
| T-213 | Session timeout config polish (FR-003) | XS | 6.4 |
| T-215 | response_model accuracy polish | XS | 6.4 |
| T-226 | Reconcile OpenAPI version (plan.md 3.1 vs openapi.yaml 3.0.3) | XS | 6.4 |
| T-227 | Align EvaluatorResult entity definition | XS | 6.4 |
| T-229 | Replace subjective qualifiers in FR-014/FR-016 | XS | 6.4 |
| T-242 | Add `schema` field to `AcceptedQuerySummary` in OpenAPI schema | XS | 6.4 |
| T-244 | Document co-located test-file convention in style guide | XS | 6.4 |
| T-246 | Tighten E2E mock route ordering | XS | 6.5 |
| T-247 | Add debounce to HistoryList filter input (SC-007) | XS | 6.5 |
| T-249 | Display `llm_provider` and `database_connection_id` in HistoryDetail | XS | 6.5 |
| T-250 | Verify user identifier in session events and diagnostic logs (closes /speckit.analyze A3) | S | 6.4 |
| T-251 | Add operator-effort assertion for provider switch under 5 min (closes /speckit.analyze A4) | XS | 6.2 |
| T-252 | Add FR/SC for null/empty SQL from LLM (closes /speckit.analyze A7) | XS | 6.4 |

### Polish deferred beyond Wave 6
| Task | Defer to | Reason |
|---|---|---|
| T-187 | Phase 2+ | Backend coverage gate + CI threshold (infra not ready) |
| T-188 | Phase 2+ | Frontend coverage gate + CI threshold (infra not ready) |
| T-189 | Phase 2+ | Unified CI workflow (depends on T-187/T-188) |
| T-190 | Phase 2+ | SC coverage suite (depends on E2E full-stack) |
| T-191 | Phase 6 | Performance-budget verification (observability) |
| T-191b | Phase 6 | Replace per-request Redis instantiation (performance tuning) |
| T-192 | Phase 2+ | quickstart.md verified on fresh machine (depends on T-189) |
| T-193 | Phase 2+ | Operator runbook (depends on T-189) |
| T-194 | Phase 6 | Security-review checklist (advanced security) |
| T-214 | Phase 6 | Rate limiting (quota enforcement, Principle X) |
| T-217 | Phase 6 | Diagnostic log retention, access control, PII handling (Principle IX) |
| T-218 | Phase 2+ | SC-001 measurement boundary spec (docs debt) |
| T-219 | Phase 2+ | Map plan.md p95 backend latency goal to SC (docs debt) |
| T-220 | Phase 2+ | Map T-101/T-102 to FR or SC (docs debt) |
| T-222 | Phase 2+ | Inline glossary or hyperlink for R-007/R-008 (docs debt) |
| T-223 | Phase 2+ | Specify schema-context-overflow threshold (docs debt) |
| T-224 | Phase 2+ | Add FR for execution-phase database error handling (docs debt) |
| T-225 | Phase 2+ | Add FR/SC for "last automatic try" UI indicator (docs debt) |
| T-228 | Phase 2+ | Clarify FR-014 result pagination (docs debt) |
| T-231 | Phase 2+ | Upgrade E2E specs to full-stack (depends on docker-in-CI) |
| T-233 | Phase 6 | Re-evaluate Inv 4 byte-equal vs structural-equal (constitutional amendment) |
| T-237 | Phase 4+ | Server-side filter repository methods (already deferred per FR-022) |
| T-240 | Phase 2+ | Re-evaluate HistoryList table vs list/card layout (UX design debt) |
| T-243 | Phase 2+ | Upgrade Wave 5 E2E to full-stack (depends on T-231) |
| T-245 | Phase 5 | Translate 11 Arabic history i18n keys (constitution §11 commitment) |
| T-248 | Phase 2+ | Defer or eliminate COUNT(*) on first-page history requests (optimization) |

---

## 2. Chunked impl plan

### Chunk 6.2 — Backend US-5 acceptance tests + operator-effort assertion  (~35 min)
- Tasks: T-174, T-176, T-177, T-251
- Test-first pairs:
  - `backend/tests/integration/test_us5_provider_switch.py` (T-174)
  - `backend/tests/integration/test_us5_ollama_routing.py` (T-176)
  - `backend/tests/integration/test_us5_reconfigured_provider.py` (T-177)
  - `backend/tests/unit/test_us5_operator_effort.py` (T-251)
- Notes: Uses httpx mocks to verify adapter routing. T-251 adds a lightweight timing assertion for SC-008.

### Chunk 6.3 — Frontend US-6 lint + i18n verification  (~35 min)
- Tasks: T-179, T-180, T-181, T-182, T-183
- Test-first pairs:
  - `npm run lint` with zero no-inline-string-literals violations (T-179)
  - `npm run lint:css` with zero physical-direction violations (T-180)
  - Production CSS bundle grep for `ml-` / `mr-` / `pl-` / `pr-` (T-181)
  - `frontend/scripts/verify-i18n-keys.ts` (T-182)
  - `frontend/tests/unit/i18n-render.test.tsx` (T-183)
- Notes: ESLint/Stylelint configs are already in place from Foundation (T-019/T-020). This chunk verifies the codebase is actually clean.

### Chunk 6.4 — Backend i18n consistency + docs/contract Polish  (~40 min)
- Tasks: T-184, T-213, T-215, T-226, T-227, T-229, T-242, T-244, T-250, T-252
- Test-first pairs:
  - `backend/tests/unit/test_message_keys.py` (T-184)
  - `backend/tests/unit/test_session_event_attribution.py` (T-250)
  - Contract test for `AcceptedQuerySummary.schema` field (T-242)
- Notes: Heavy docs/contract chunk. T-226, T-227, T-229, T-252 update spec.md and openapi.yaml. T-244 adds `docs/style-guide.md`.

### Chunk 6.5 — E2E + final FE Polish  (~50 min)
- Tasks: T-178, T-185, T-186, T-246, T-247, T-249
- Test-first pairs:
  - `frontend/tests/e2e/provider-switch.spec.ts` (T-178)
  - `frontend/tests/e2e/i18n-audit.spec.ts` (T-185, T-186)
  - `frontend/tests/e2e/helpers/mock-backend.ts` fix (T-246)
  - `frontend/src/components/history/HistoryList.test.tsx` debounce assertion (T-247)
  - `frontend/src/components/history/HistoryDetail.test.tsx` field render assertion (T-249)
- Notes: E2E specs continue to use Playwright `page.route()` mocks until docker-in-CI (T-231) lands in Phase 2+.

### Chunk 6.7 — Gemini audit (DRAFT PR, never merged)
- Scope: Full pass over US-5 + US-6 + rolled-in Polish changes.
- Deliverable: Audit report in `tmp/wave-6/audit-gemini.md`.

### Chunk 6.8 — Opus audit (DRAFT PR, never merged)
- Scope: Independent second audit over the same delta.
- Deliverable: Audit report in `tmp/wave-6/audit-opus.md`.

### Chunk 6.9 — triage + fixes (Wave 6 + Phase 1 ships)
- Tasks: Triage findings from 6.7 and 6.8; apply fixes; mark tasks `[x]`; generate `wave-6-snapshot.md`.
- Deliverable: Final snapshot doc; PR merged to main; Phase 1 closeout begins.

---

## 3. New tasks registered during /speckit.analyze

- **T-250**: Verify user identifier attribution in session events and diagnostic logs (closes /speckit.analyze A3). Cluster: Polish. Effort: S. Dependencies: T-051. FR/SC: FR-027.
- **T-251**: Add operator-effort assertion for LLM provider switch under 5 minutes (closes /speckit.analyze A4). Cluster: US-5. Effort: XS. Dependencies: T-174. FR/SC: SC-008.
- **T-252**: Add FR/SC for null/empty SQL from LLM (closes /speckit.analyze A7). Cluster: Polish. Effort: XS. Dependencies: T-224. FR/SC: FR-010 extension.

---

## 4. Foundation gates at plan time

- Backend pytest (-m "not integration"): **282 passed**, 66 skipped
- Frontend tests: **108 passed**
- Lint/typecheck/build: **clean**
- Playwright enumeration: 29 specs in 7 files

---

## 5. Phase 1 closeout pre-conditions

After Wave 6 ships:
- All P1 + P2 user stories implemented and tested (US-1 to US-5; US-6 is P3 foundation).
- All Phase 1 constitution principles (I, II, III, V, VIII) enforced.
- Polish deferrals explicitly mapped to future Phases (see deferral table above).
- Final snapshot doc generated (`wave-6-snapshot.md` → `phase-1-snapshot.md`).
- `/speckit.analyze` remediation tasks T-250..T-252 closed or re-deferred with rationale.
