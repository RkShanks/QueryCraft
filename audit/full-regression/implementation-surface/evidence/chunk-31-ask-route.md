# CHUNK-31 — legacy `/ask` retirement

Status: **Resolved** for `IS-GAP-045` on tested product head `5eaa62d05d83e22a268e6107916348d7644651ed`, from starting main `04c455584c51ae8ba40cdd252272192a564850fb` on branch `phase-6/wave-19.31-ask-route-disposition` through [#344](https://github.com/RkShanks/QueryCraft/pull/344).

This evidence is value-safe. The browser proof used deterministic placeholder prompt and connection values, disabled screenshots/video/traces, intercepted every application API request and executed no source query or LLM request. No credential, cookie, API response body, prompt value, SQL value or browser artifact is retained here.

## Result

The normal protected-route catalog no longer contains `/ask`. A small pre-provider compatibility boundary recognizes that exact pathname, reads only `question`, `connectionId`, and `lng`, stores the two Workspace prefills only in short-lived React state, and immediately navigates to `/` with `replace: true`. The destination URL therefore contains at most normalized locale input; unknown parameters and every fragment are discarded. Direct URLs, bookmarks, reload, back and forward cannot remount the deleted legacy page.

Workspace remains guarded by exactly `query.submit`. Authentication and permission decisions occur before Workspace feature hooks mount. An unauthenticated bookmark reaches the existing localized sign-in contract without a return URL; a user lacking `query.submit` reaches localized access denied. Each denial path issued one authorization request and zero feature or submit requests. The authenticated browser matrix issued one authorization request, exactly one sessions/connections/query-limits request set, and zero submit requests.

Workspace consumes the prompt only as its existing editable prefill and never submits it automatically. It applies a supplied connection only after the authorized user-connections response contains that usable connection; unavailable identifiers are ignored. Both handoff state and direct Workspace `question`/`connectionId` parameters are consumed with history replacement, leaving no sensitive prompt or connection residue in the settled URL/history. Locale normalization, precedence, document `lang`/`dir`, persistence and manual switching were not changed.

EN and AR titles settle directly to `Workspace | QueryCraft` and `مساحة العمل | QueryCraft`. The removed Ask title never appeared in the observed mutation history. The production-built SPA returned HTTP 200 for a direct `/ask` request through real Nginx SPA fallback with the exact strict CSP and no `unsafe-eval`.

## Retirement and caller sweep

The duplicate state machine and its Ask-exclusive graph were removed after route, bookmark, authorization and production-browser replacement proof passed:

- `frontend/src/pages/AskQuestionPage.tsx` and its test;
- legacy query `QueryInput`, `QueryActions`, `ResultTable`, `SqlDisplay`, `RefinePromptBanner`, and `TimeoutBanner`, plus the five paired component tests;
- four Ask-only Playwright workflows for legacy timeout/reject/refine/error behavior;
- the `/ask` document-title entry, Ask-only EN/AR locale keys and obsolete i18n/classification rows.

The provider-switch workflow was migrated to the primary Workspace behavior. Static caller searches found no remaining production caller for any deleted module. The similarly named chat result components remain reachable, and `frontend/src/hooks/useQuerySubmit.ts` remains in use by Workspace. No unrelated dead-export cleanup was performed.

## TDD history

- Route boundary: RED `7aa5e61` → GREEN `5ee039e`.
- Supported bookmark handoff: RED `89820ca` → GREEN `546da49`.
- Authorized Workspace consumption: RED `7fb5728` → GREEN `f43aa4a`.
- Authorization and denial boundaries: coverage `24d1c69`.
- Proven Ask-exclusive removal: refactor `baf3f0d`.
- Production Nginx/history/title/request proof: RED `e79bc87` → GREEN `4a68a4f`.
- Connection-authorization failure settlement: RED `7708e8e` → GREEN `5eaa62d`.

The first production-browser RED run exposed prefill loss when URL cleanup remounted the query provider; moving the two non-locale values into the short-lived pre-provider handoff fixed that integration boundary. The next RED run exposed a redundant authorization request on permission denial; carrying only the verified authorization identity across the replace redirect removed the duplicate without changing the decision or adding a return-URL contract.

## Browser proof

The exact production build ran behind a real Nginx container with the deployed strict CSP. The focused Chromium spec passed **8/8**:

- authenticated EN and AR bookmarks at 1440×900, 768×1024 and 375×812;
- `/ask?question=...&connectionId=...&lng=...` with an unknown parameter and fragment;
- localized unauthenticated and no-`query.submit` personas;
- direct load, bookmark, back, forward and reload behavior;
- Workspace prefill and authorized connection selection with zero automatic submissions;
- exact request counts, settled URL, title history, `lang`/`dir`, legacy-DOM absence, raw-key absence and root/body overflow;
- zero unexpected console/page errors and zero CSP violations.

The direct Nginx probe returned HTTP 200 `text/html`, `Cache-Control: no-store` and the exact deployment headers for `/ask?question=probe&lng=en`. Browser screenshots, video and traces were off.

## Gates

- Focused App/router, permission, title and Workspace tests: 82 passed.
- Full frontend Vitest: 101 files, 1,350 tests passed.
- Focused production-Nginx Playwright Chromium: 8 passed, 0 failed.
- ESLint, TypeScript typecheck and CSS lint: pass.
- Production build: pass, 2,325 modules; existing large-chunk warning only.
- Generated API currentness and generated contract/compatibility: pass; runtime = canonical = generated remains **65 = 65 = 65**.
- Test-harness guard: pass; 41 Playwright specs classified.
- Relevant backend authorization compatibility: 51 passed, 5 skipped; Ruff check/format pass with 143 files already formatted.
- EN/AR JSON parsing, E2E classification JSON, links, accounting, static callers, locale-key leakage, generated artifacts and `git diff --check`: pass.
- Regression coverage for Workspace submit/result/reject/regenerate/history, CHUNK-01 source continuity, CHUNK-07 permissions, CHUNK-08 prompt limits, CHUNK-21 cancellation, CHUNK-28 privacy and CHUNK-30 CSP/title/validator policy remained green through the focused and full suites.
- Test Guard, Clean Code Guard, Vercel React review and Docs Guard: pass with no remaining finding.

## Isolation and cleanup

The proof used one disposable Nginx container, one local production frontend image and loopback port 18031. All were removed after proof; no disposable container, image, browser artifact or listener remains. API interception made backend, database, Redis, source and LLM services unnecessary.

All 23 pre-existing protected PNG/screenshot/trace files retain their starting tracked hashes and working-tree status; none was staged. Exact-path staging was used and `git add -A` was never used. Draft PR #336 was not changed.

`IS-GAP-015` remains **Partial** because non-Gemini live smoke is deferred until approved credentials/runtime exist; external/non-Gemini LLM calls remain zero. `IS-GAP-018` remains **Partial** because vendor checksum provenance is unavailable. Neither row is falsely closed.

Post-merge accounting is **Resolved 45, Pending 0, Partial 2, Needs Decision 0, Total 47**. CHUNK-31 is complete and no implementation-pending gap remains. T-905 and Phase 6 freeze work were not started.
