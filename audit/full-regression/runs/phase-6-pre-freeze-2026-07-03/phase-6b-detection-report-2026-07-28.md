# Phase 6B Hostile-Input Detection Current-Head Regression

Run date: 2026-07-28

Scope: hostile-input detection only. Phase 6C audit hardening, final Phase 6 closure, T-905, freeze work, and the implementation-surface gap audit were not started.

Starting synchronized main HEAD: `58d74aa357464ccc1997f0436092539390e88784`

Tested product HEAD: `ef525f0e6d13f8a497693322689b985679e75dee`

Runtime: isolated platform database and Redis DB 15, deterministic pipeline and failure spies, real backend APIs, a configured real LLM for one benign downstream check, headless Chromium, and Chrome DevTools MCP.

## Result

| Status | Count |
|---|---:|
| Pass | 10 |
| Fail | 0 |
| Partial | 0 |
| Setup-dependent | 0 |
| Not run | 0 |
| Deferred | 0 |

## Requirement Matrix

| ID | Status | Automated Evidence | Browser/API Evidence | Notes |
|---|---|---|---|---|
| P6-FR-156 | Pass | Package-registration, registry, detector, fail-closed, query-pipeline, and sanitization tests passed in the 672-test focused matrix and full backend gate. Tests cover exactly five production rules, all-rule execution, allowed/flagged/blocked aggregation, exact thresholds, and sanitized failure before every downstream spy. | Eight concurrent cold-start reads returned 200 and produced one singleton row. Missing and corrupt configuration returned sanitized 503 responses before quota; the blocked response contained only `message_key`. | Missing configuration, incomplete registry state, rule exceptions, and invalid results cannot silently disable detection or reach quota, evaluator, LLM, chat, history, session, or attempt creation. |
| P6-FR-157 | Pass | All five categories passed English and Arabic clear-hostile and weaker-signal coverage: prompt injection, SQL injection, RBAC bypass, schema exposure, and destructive SQL. | Representative blocked and flagged events were exercised through the isolated API; the browser rendered the blocked state without category or rule detail. | Strong cases block and weaker cases flag according to configured thresholds. |
| P6-FR-158 | Pass | HostileInputBlockedBanner and WorkspacePage submit suites passed 16/16; full Vitest passed 65 files and 786 tests. Sanitization suites verify the response excludes category, rule, confidence, pattern, explanation, hash, input, provider detail, and stack data. | Chrome verified localized EN/LTR and AR/RTL blocked banners. In both locales the textbox cleared, the rejected user bubble was removed, and value-safe DOM scans reported no rejected-input echo. The real 400 API body contained only `message_key`. | A reproduced browser echo was fixed in PR #247. No hostile value is retained in the rendered blocked turn. |
| P6-FR-159 | Pass | Deterministic ordering tests verify detection before quota before evaluator/LLM, no blocked downstream work, and exactly one quota call for flagged/allowed requests. The flagged audit is committed before the single quota call. | Blocked attempts left quota unchanged and created no chat/session/attempt/history. One benign real-LLM request passed detection and reached downstream generation/evaluation, where evaluator policy still returned a sanitized 422. | Detection does not replace evaluator authorization. |
| P6-FR-160 | Pass | Bypass coverage passed for case, whitespace, punctuation, multiline input, SQL comments, zero-width characters, Unicode compatibility forms, bidi controls, Arabic diacritics/tatweel, and mixed EN/AR text. The long-input runtime check remained below its two-second bound. | No browser check was required beyond the localized blocked flow. | Benign coverage includes union membership, deleting a saved query, a drop in revenue, ignoring null values, schema documentation, and equivalent Arabic business language. The contract is bounded heuristic canonicalization, not arbitrary encoding or semantic-attack detection. |
| P6-FR-161 | Pass | Registry tests cover register/list, duplicate rejection, a structurally valid custom rule, fresh package import, stable repeated imports, and exactly five built-ins. Detector integrity checks fail closed for invalid production registry state. | The concurrent cold-start API check returned eight successful reads with one durable singleton configuration row. | Extensibility remains available without allowing an empty, incomplete, or corrupt production registry to bypass detection. |
| P6-FR-162 | Pass | Admin configuration tests cover equality, reversed thresholds, exact bounds, out-of-range values, malformed JSON, nulls, strings, booleans, NaN/Infinity, missing fields, permissions, audit emission, and concurrent singleton initialization. Frontend page tests and all frontend gates passed. | Real GET/PUT succeeded only with `admin.security.manage`. Restricted, quota-only, and legacy lowercase `admin` sessions received sanitized 403 for both methods. Chrome verified EN/AR desktop read/update and localized validation. Live Playwright passed EN/AR at 375px and 768px with visible controls and no horizontal clipping. | The durable `detection.config.change` context contained only `block_confidence_updated` and `flag_confidence_updated` booleans; its leakage scan was false. |
| P6-FR-163 | Pass | Blocked/flagged durability, redaction, query integration, audit search/export, and no-raw-payload suites passed. Ordering spies prove flagged input continues once and blocked input stops immediately. | A quota-denied flagged event increased the durable audit count by one. Three blocked requests increased it by three. Real audit search and export both returned 200, and value-safe scans found no original rejected value. | Stored detection context is limited to category, outcome, rule-name list, confidence metadata, the constant redaction marker, and input hash. |
| P6-FR-164 | Pass | Redaction suites verify raw input and matched explanations are absent at every context key. A deterministic audit-write-failure composition check passed: sanitized context reached the audit call, its exception propagated, and all quota/session/history/attempt/LLM/evaluator/executor spies remained untouched. | Blocked and flagged API contexts passed value-safe leakage scans; the blocked response and browser contained no rejected value. | Audit failure cannot expose hostile text or turn a blocked request into an allowed request. |
| P6-FR-165 | Pass | Detection and lifecycle suites verify no suspension/lockout behavior is implemented by repeated hostile outcomes. | Three repeated blocked attempts left user and role records unchanged, emitted zero suspension events, consumed no quota, and preserved a 200 authenticated session. A later benign request remained usable and reached downstream authorization. | No hidden lockout, role mutation, user mutation, or unsupported suspension audit event occurred. |

## Regression Fixes

- [PR #243](https://github.com/RkShanks/QueryCraft/pull/243) — **High**: closed Unicode/comment/formatting bypass-normalization gaps while preserving benign schema-documentation and business-language inputs.
- [PR #244](https://github.com/RkShanks/QueryCraft/pull/244) — **High**: made missing/corrupt configuration, incomplete production registry state, and rule failures return sanitized fail-closed 503 responses before downstream work.
- [PR #245](https://github.com/RkShanks/QueryCraft/pull/245) — **Mid**: rejected numeric strings and booleans instead of coercing detection thresholds.
- [PR #246](https://github.com/RkShanks/QueryCraft/pull/246) — **High**: made flagged hostile-input audit events durable when the later quota transaction is denied.
- [PR #247](https://github.com/RkShanks/QueryCraft/pull/247) — **High**: removed rejected hostile input from the rendered workspace and blocked-turn state.

Each fix used a RED-before-GREEN regression, passed `backend-test` and `frontend-test`, was squash-merged, and had its branch deleted.

## Automated Validation

| Gate | Result |
|---|---|
| Discovered detection/rule/config/audit/query/quota-ordering/evaluator/sanitization selection (42 current files) | 672 passed; 11 skipped |
| Deterministic blocked-audit-write-failure composition check | 1 passed |
| Full backend pytest on tested product HEAD | 2,612 passed; 15 skipped; 5 non-failing warnings; 35 subtests passed |
| Ruff check | Pass |
| Ruff format check | Pass; 398 files already formatted |
| Focused WorkspacePage and HostileInputBlockedBanner suites | 16 passed |
| Full Vitest on the source squash-merged as tested product HEAD | 65 files passed; 786 tests passed |
| ESLint | Pass |
| TypeScript typecheck | Pass |
| Production build | Pass; non-failing chunk-size warning |
| CSS lint | Pass |
| Live responsive Playwright check | 1 passed; four locale/viewport combinations |
| Fix PR CI | `backend-test` and `frontend-test` passed for PRs #243 through #247 |
| `rtk git diff --check` | Pass |

The full affected gate commands included:

| Command | Result |
|---|---|
| `cd backend && rtk uv run pytest -q` | 2,612 passed; 15 skipped; 5 warnings; 35 subtests passed |
| `cd backend && rtk uv run ruff check src tests` | Pass |
| `cd backend && rtk uv run ruff format --check src tests` | Pass; 398 files already formatted |
| `cd frontend && rtk npm test -- --run` | 65 files passed; 786 tests passed |
| `cd frontend && rtk npm run lint` | Pass |
| `cd frontend && rtk npm run typecheck` | Pass |
| `cd frontend && rtk npm run build` | Pass; non-failing chunk-size warning |
| `cd frontend && rtk npm run lint:css` | Pass |

## Browser and API Verification

- Chrome DevTools MCP verified the real Admin Detection page at desktop width in English/LTR and Arabic/RTL. A live update succeeded; equality validation was localized in both languages.
- Headless Chromium exercised 375x812 and 768x1024 in both locales. Threshold inputs and the save action remained visible, the document did not overflow, and no control crossed the viewport.
- The real permission matrix allowed only the explicit security-management permission. All three insufficient session shapes returned the two-field sanitized forbidden envelope.
- The current-head validation matrix accepted only the exact legal boundaries and returned the generic validation message key for every malformed, missing, non-numeric, non-finite, out-of-range, equal, or reversed input.
- The blocked API response was a sanitized 400. Chrome verified localized banners, an empty textbox, no rejected user bubble, and false DOM leakage scans in both languages.
- Durable blocked and flagged events were searchable/exportable, while original-value scans were false. Repeated blocked requests preserved quota, identity, role, and session state.
- One benign request used the configured real LLM only to confirm passthrough. It reached the evaluator and was denied by evaluator policy, proving downstream authorization remained active.

## Isolation, Leakage, and Cleanup

- Repeated attempts, threshold mutations, audit inspection, and permission sessions used `querycraft_phase6b_20260728` and Redis DB 15, separate from normal development state.
- Evidence contains no hostile probe, matched pattern, credential, cookie, session identifier, provider detail, raw audit row, stack trace, or internal configuration value.
- Value-safe scans compared sensitive values in memory and retained only boolean results, public statuses/message keys, counts, contract field names, and the fact that approved hashes were present.
- The isolated application and Vite servers were stopped. The disposable platform database was dropped, Redis DB 15 was flushed, and temporary probe/config/test files were deleted.
- Pre-existing dirty Phase 5 PNGs and historical Phase 1/2 screenshots/traces were not staged, edited, deleted, or reverted. No fresh screenshot was required or staged.

Phase 6B is complete at 10/10 Pass. Phase 6C is unblocked but was not started.
