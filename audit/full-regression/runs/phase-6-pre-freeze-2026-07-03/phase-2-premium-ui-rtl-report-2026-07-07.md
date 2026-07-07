# Phase 2 Premium UI / RTL Regression Report - 2026-07-07

Scope: Phase 2 matrix rows only. Phases 3-6, T-905, and freeze work were not started.

## Tested Revision

- Branch: `main`
- HEAD: `43000af7cb7eb4f72374b5d1c6fca79708d2c1a7`
- Requested base main: `43000af7cb7eb4f72374b5d1c6fca79708d2c1a7`
- Fix branch under test: `fix/phase2-response-card-actions` based on `43000af7cb7eb4f72374b5d1c6fca79708d2c1a7`
- Evidence branch/PR: blocker fix PR pending; Phase 2 real-user response-card rows must be rerun on `main` after merge before Phase 2 closure.
- Worktree guard: pre-existing dirty Phase 5 PNG evidence and old full-regression screenshots/traces were present before this run. They were not staged or intentionally modified.

## 502 Root Cause Classification

The original live submit `502` was isolated as setup/provider-dependent, not a confirmed product blocker.

Evidence:

- Backend/frontend/source containers were rebuilt and recreated from current `main` with `docker compose -f docker-compose.dev.yml up -d --build --force-recreate`.
- `.env` provider/platform/source/admin configuration keys were present; values were not printed.
- `seed_e2e_connection.py` repaired and verified `source_analytics`, `MySQL Sakila`, and `MSSQL AdventureWorks`: all healthy, schema introspected, Admin policy present.
- One signed-in Admin direct API submit against `source_analytics` succeeded with HTTP 200, `kind=result`, `row_count=5`, two columns, and generated SQL present.
- The current browser live submit then returned HTTP 502. Backend log showed Gemini `generateContent` returned HTTP 429 Too Many Requests.
- A direct API retry also returned HTTP 502 with sanitized `error.llmUnavailable`; backend log again showed Gemini HTTP 429.
- Later live-LLM retry: two bounded signed-in Admin direct API submit attempts against `source_analytics` both returned HTTP 502 with sanitized `error.llmUnavailable` and no generated SQL. Backend logs showed Gemini `generateContent` HTTP 429 Too Many Requests for the retry.
- Owner updated the Gemini API key. Backend was force-recreated to pick up the new `.env` value. After recreation, direct Admin API submit and browser live submit/follow-up returned HTTP 200.

Classification: the Gemini 429/provider quota blocker is resolved after the key update and backend recreation. Not source connection/decryption drift, not app product error, and not stale container/runtime mismatch after rebuild/recreate.

The provider-side 502 gap is closed. A separate product blocker was then confirmed in the response-card action path: live submit returned both `attempt_id` and `accepted_query_id`, but session-history dedupe replaced the live local turn with a saved-history card that did not carry an active attempt ID. Saved accepted-query IDs are not valid regenerate substitutes and returned sanitized HTTP 422 `error.attemptInvalid` / `attempt_not_active`.

Fix-branch verification: `fix/phase2-response-card-actions` decoupled copy from regenerate and changed workspace turn merging to prefer a live local turn with an active attempt ID over the duplicate saved-history row. Focused real-browser verification on rebuilt containers showed live submit HTTP 200 with copy/regenerate/delete visible, copy clicked, regenerate request used the original active `attempt_id` and not the `accepted_query_id`, regenerate returned HTTP 200 `kind=result`, and no raw provider errors, keys, stack traces, DB hosts/passwords, or untranslated keys appeared.

## Commands Run

| Command | Exit | Notes |
|---|---:|---|
| `pwd && git status --short && git rev-parse HEAD && git branch --show-current` | 0 | Confirmed `/home/avril/QueryCraft`, `main`, requested SHA, and pre-existing dirty/untracked evidence. |
| `sed -n ... AGENTS.md`, `.agents/ORCHESTRATOR.md`, Phase 2 matrix/runbook/report, Phase 5 plan | 0 | Required handoff and scope docs read. |
| `docker compose -f docker-compose.dev.yml up -d --build --force-recreate` | 0 | Rebuilt backend/frontend and recreated all dev stack containers. |
| `docker compose -f docker-compose.dev.yml ps` | 0 | Backend/frontend up; platform/source Postgres, Redis, MySQL, and MSSQL healthy. |
| Redacted `.env` presence check | 0 | Required keys present; no secret values printed. |
| `docker compose -f docker-compose.dev.yml exec -T backend ... src/seed_e2e_connection.py` | 0 | Restored/verified PG/MySQL/MSSQL source connections and Admin policies. |
| Direct Admin API submit probe | 0 | Sign-in 200; connections 200; session create 201; `source_analytics` submit 200 result. First raw probe without Origin/cookie handling produced expected setup-only 403/401 and was corrected. |
| Current browser Playwright live-submit probe | 1 | Sign-in/source selection passed; browser query submit returned 502. Backend log classified Gemini HTTP 429. |
| Direct Admin API retry | 0 | Submit retry returned 502 with sanitized `error.llmUnavailable`; backend log showed Gemini HTTP 429. |
| Current browser Playwright non-provider UI checks | 0 | Sign-in, New Chat clear, source selection, sidebar grouping, session switch/isolation, delete/undo/permanent delete, settings update/restore, Arabic RTL, and mobile smoke passed. |
| Later bounded Direct Admin API live retry | 0 | Two attempts: sign-in/connections/session creation succeeded; both `POST /query/submit` attempts returned 502 with sanitized `error.llmUnavailable`. Backend log showed Gemini HTTP 429. |
| Backend recreate after Gemini key update | 0 | Backend force-recreated so the process picked up the updated `.env` value. |
| Direct Admin API submit after key update | 0 | Sign-in/connections/session creation passed; `POST /query/submit` returned 200 result with five rows and generated SQL present. |
| Browser live submit/follow-up after key update | 1 | Live submit and follow-up both returned 200 and rendered response cards. Harness then stopped on absent regenerate control. |
| Session/history verification after key update | 0 | Session detail API showed two saved attempts with result payloads; browser history listed the follow-up, live first turn, and direct API smoke rows. |
| `cd frontend && rtk npm test -- --run AssistantResponseCard` | 0 | RED first failed on missing copy without active attempt, then passed after action-bar fix. |
| `cd frontend && rtk npm test -- --run WorkspacePageSubmit` | 0 | Added regression for saved-history refresh preserving live attempt actions; 13 tests passed. |
| `cd frontend && rtk npm test -- --run WorkspacePage AssistantResponseCard CodeBlockActionBar` | 0 | Focused requested frontend suite passed: 7 files, 33 tests. |
| `cd frontend && rtk npm run lint` | 0 | ESLint passed. |
| `cd frontend && rtk npm run typecheck` | 0 | TypeScript passed. |
| `cd frontend && rtk npm run lint:css` | 0 | Stylelint passed. |
| `cd frontend && rtk npm run build` | 0 | Production build passed; existing Vite chunk-size warning only. |
| `docker compose -f docker-compose.dev.yml up -d --build --force-recreate frontend` | 0 | Rebuilt/recreated frontend; compose also recreated backend, so seed verification was rerun. |
| Fix-branch browser response-card/regenerate probe | 0 | Sign-in, source selection, live submit, copy, regenerate, and post-regenerate controls passed on rebuilt containers. |

Additional evidence: `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-2-current-head-browser-evidence-2026-07-07.json`.

## Browser/API/Real LLM Checks

| Check | Status | Evidence |
|---|---|---|
| Local admin sign-in | Pass | Browser sign-in reached workspace; direct API sign-in returned Admin role with eight permissions. |
| New Chat/session creation | Pass API / Pass browser clear | Direct API session creation returned 201. Browser New Chat cleared active sidebar selection; prompt focus was not observed under current shell. |
| Source connections | Pass | Browser/API showed `source_analytics`, `MySQL Sakila`, and `MSSQL AdventureWorks`; seed verification reported all healthy/introspected with Admin policy. |
| Sidebar session list/grouping | Pass | Browser showed Today grouping and current successful live-result session preview. |
| Session switching/workspace isolation | Pass | Browser switched between empty and populated sessions; the empty session did not show the populated question, and the populated session did. |
| Delete session and undo restore | Pass | Browser delete showed undo toast; Undo restored session. Second delete expired after 5.6 seconds and removed throwaway session. |
| Direct live submit | Pass | Signed-in Admin direct API submit against `source_analytics` returned HTTP 200 result. |
| Later direct live retry | Pass | After the owner updated Gemini key and backend was recreated, signed-in Admin direct API submit returned 200 result. |
| Browser live submit | Pass | Browser New Chat live submit returned 200 through `/query/submit` and rendered a response card with result table, SQL block, and delete action. |
| Follow-up query uses prior context | Pass live / Pass automated | Browser follow-up in the same session returned 200 and rendered a second response card; session detail later showed two saved attempts. |
| LLM context cap read/update/restore | Pass | Browser settings read cap `3`, updated to `2`, then restored to `3`. |
| Regenerate replacement result | Pass on fix branch | Current `main` had no visible regenerate control. On `fix/phase2-response-card-actions`, live card rendered regenerate and `/query/regenerate` returned HTTP 200 `kind=result` using the active `attempt_id`, not the saved `accepted_query_id`. |
| Session/history reflects saved attempts | Pass | Session detail API showed the live browser session with two saved attempts and result payloads. Browser history listed the follow-up, live first turn, and direct API smoke rows with `source_analytics` metadata. |
| Response-card current contract | Pass on fix branch | Browser live response card showed SQL block, result table, metadata, copy, regenerate, and delete. Old thumbs/accept/reject UI was absent, consistent with current contract. |
| Arabic/RTL Phase 2 surfaces | Pass | Browser `/?lng=ar` had `dir=rtl`, `lang=ar`, and Arabic New Chat text. Prior RTL/i18n e2e gates passed in the existing report history. |
| Mobile/basic responsive | Pass | Browser 390x844 Arabic workspace had no horizontal document overflow. |
| Browser/API leakage | Pass | Evidence and observed API/browser output did not print secrets, cookies, provider keys, DB passwords, raw tokens, or provider payloads. |

## Matrix Results

| Matrix Row | Status | Evidence | Notes |
|---|---|---|---|
| P2-FR-031 | Pass | Direct API session create 201; browser New Chat cleared active workspace selection. | Prompt focus not observed; treated as current-shell drift, not blocker. |
| P2-FR-032 | Pass | Browser switched between populated and empty sessions; session detail API 200. | Populated session came from the successful direct live API submit. |
| P2-FR-033 | Pass | Browser delete/undo restore passed; permanent expiry removed throwaway session. | Current HEAD evidence refreshed. |
| P2-FR-034 | Pass | Browser sidebar showed Today grouping and current preview. | Current HEAD evidence refreshed. |
| P2-FR-035 | Pass | Browser live follow-up returned 200 in the same session after Gemini key update; session detail showed two saved attempts. | Live context path refreshed on current HEAD. |
| P2-FR-036 | Pass | Existing automated feedback suites passed in prior gate run; current response delete/autosave state visible. | Old explicit thumbs UI absent from current workspace. |
| P2-FR-037 | Pass on fix branch | Focused browser probe on `fix/phase2-response-card-actions` showed copy visible on successful live submit and still visible after regenerate. | Needs rerun on `main` after fix PR merge. |
| P2-FR-038 | Pass on fix branch | Focused browser probe showed regenerate visible, request body used the active `attempt_id`, did not use `accepted_query_id`, and returned HTTP 200 `kind=result`. | Needs rerun on `main` after fix PR merge. |
| P2-FR-039 | Pass | Existing feedback API/component coverage passed in prior gate run. | Old thumbs UI absent from current workspace contract. |
| P2-FR-040 | Pass | Browser settings read/update/restore passed: `3 -> 2 -> 3`. | Current HEAD evidence refreshed. |
| P2-FR-041 | Pass | Browser Arabic route showed `dir=rtl`, `lang=ar`, Arabic New Chat text. | Existing RTL/i18n e2e gates also green. |
| P2-FR-042 | Pass | Browser historical response card showed SQL code block. | Current HEAD evidence refreshed. |
| P2-FR-043 | Pass | Browser sidebar displayed current preview text from first user message. | Current HEAD evidence refreshed. |
| P2-FR-044 | Pass | Existing session deletion integration coverage passed in prior gate run; browser permanent delete removed throwaway session. | No product blocker. |
| P2-FR-045 | Pass | Session detail loaded accepted query with session association and result payload. | Current contract includes later-phase metadata. |
| P2-FR-046 | Pass | Browser admin settings GET/PATCH returned 200 and restored original value. | Current HEAD evidence refreshed. |
| P2-FR-047 | Pass | Simulated Gemini contract tests passed in prior gate run; after key update direct and browser live submits returned 200. | Provider quota blocker cleared. |
| P2-FR-048 | Pass | Lifecycle invariant tests passed in prior gate run. | No browser check required. |
| P2-FR-049 | Pass | Browser desktop shell usable; 390x844 Arabic workspace had no horizontal overflow. | Current HEAD evidence refreshed. |
| P2-FR-050 | Pass on fix branch | Browser live response cards showed SQL/table/metadata/copy/regenerate/delete. | Explicit old thumbs/accept UI absent; current contract verified on fix branch and needs rerun on `main` after merge. |
| P2-FR-051 | Pass | Browser sidebar logo/nav/New Chat/grouped list/delete controls exercised. | Current HEAD evidence refreshed. |
| P2-FR-052 | Pass | Browser prompt and database selector exercised in EN/AR. | Prompt focus after New Chat was false; no blocker found. |
| P2-FR-053 | Pass | Browser Arabic route activated RTL shell; existing RTL component/e2e coverage remains green. | No overlap/overflow observed in mobile smoke. |
| P2-FR-054 | Pass | Existing frontend unit suite covers debounce constant. | No separate browser timing check required. |
| P2-FR-055 | Pass | Existing `lint:css` gate passed in prior report history. | No current visual physical-direction issue observed. |
| P2-FR-056 | Pass | Existing locale/i18n audit passed; Arabic browser smoke had localized visible text. | No raw key observed in refreshed browser checks. |
| P2-FR-057 | Pass | Existing i18n audit passed; refreshed browser smoke did not show raw key on checked surfaces. | No default-value evidence added. |
| P2-FR-058 | Pass automated / Browser not refreshed | Existing session in-flight behavior coverage passed in prior gate run. | Live slow-query delete/undo not rerun because provider quota blocked new live browser query. |

## Counts

- Matrix rows total: 28
- Pass: 25
- Pass on fix branch pending merge/rerun on `main`: 3
- Partial: 0
- Setup-dependent: 0
- Deferred: 0
- Failed: 0
- Product blockers found: 0
- Current real-user browser/API flows refreshed: sign-in, New Chat clear, source selection, sidebar grouping, session switch/isolation, delete/undo/permanent delete, settings update/restore, response-card render from successful live result, Arabic RTL, mobile smoke.
- Live LLM status: after the owner updated the Gemini key and backend was recreated, direct API submit, browser live submit, and browser follow-up passed. On the fix branch, browser regenerate replacement result also passed and used the active `attempt_id`.

## Security and Privacy

No secrets, cookies, provider keys, DB passwords, raw tokens, raw provider payloads, or credential values were added to evidence. Env checks printed presence only. Backend logs were inspected only far enough to classify provider HTTP 429 and sanitized app 502 behavior.

## Completion Assessment

Phase 2 automated gates remain complete and green per the prior run history, and current-HEAD real-user browser/API coverage is substantially refreshed.

Phase 2 is not fully complete for exhaustive real-user closure until the response-card fix PR is merged and the three fix-branch response-card rows are rerun on `main`. The Gemini/provider quota condition is cleared after the key update.

Phase 3 remains not unblocked by this execution because the response-card blocker fix has not yet merged and the final `main` evidence-only Phase 2 PR has not been created.

Next step before Phase 3: merge the response-card fix PR, rerun only the remaining response-card/regenerate rows on `main`, then create the Phase 2 evidence-only PR.
