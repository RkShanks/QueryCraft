# Phase 1 Browser Smoke Report

Run date: 2026-07-04
Scope: Chunk 1 only - Phase 1 browser/real-use validation

Branch tested: `main`
HEAD SHA tested: `c2184ec7e7c044cb6785093a4f6ad106004e04da`

## Summary

Browser validation passed after the backend restart refreshed the built-in local
admin state. The UI signed in through `/api/v1/auth/sign-in`, submitted a live
Gemini-backed natural-language query, rendered generated SQL and results,
accepted the result, and showed the accepted query in History.

Reject/regenerate controls were exercised from the Phase 1 `/ask` surface:
reject returned a distinct retry result and regenerate returned the expected
refine prompt. The unsafe prompt was blocked with a sanitized user-visible
security-policy message before SQL execution.

No product code or test harness code was changed. Phases 2-6 and T-905 were not
started.

## Regression Task Matrix

| Task | Status | Evidence |
|---|---|---|
| Local admin login and session expiry behavior. | Pass | UI sign-in passed through `/api/v1/auth/sign-in`; see `screenshots/phase1-rerun-02-signed-in.png` and `phase-1-browser-smoke-evidence.json`. Session expiry was not separately exercised in this browser smoke. |
| Unauthenticated users redirected away from platform features. | Pass | Initial `/api/v1/auth/me` returned 401 and the browser rendered sign-in; see `screenshots/phase1-rerun-01-open-frontend.png`. |
| Question validation rejects empty and over-length prompts. | Skipped | Not part of this requested rerun; no backend pytest rerun was requested. |
| LLM provider selection follows config and receives schema context. | Pass | Backend container reported `LLM_PROVIDER=gemini`, Gemini credential presence, and `LLM_MODEL_NAME=gemini-flash-latest`; live submit generated `SELECT COUNT(*) FROM customer`. |
| Evaluator blocks empty SQL, write/DDL SQL, unsafe PostgreSQL functions, multi-statement SQL, and missing schema objects. | Pass | Unsafe prompt returned sanitized `400 error.hostile_input_blocked` and the UI showed a generic security-policy message; no SQL/result card rendered. |
| Read-only source execution handles success, timeout, and zero-row results. | Pass | Normal query rendered `SELECT COUNT(*) FROM customer` with one result row (`599`). Timeout and zero-row variants were not part of this browser rerun. |
| Accept persists accepted query and history; rejected/evaluator-rejected SQL is not durable history. | Pass | `/api/v1/query/accept` returned 201 and `/history` listed the unique accepted question; see `screenshots/phase1-rerun-05-history-after-accept.png`. |
| Reject/regenerate allows one distinct retry and blocks byte-identical retry. | Pass | `/api/v1/query/reject` returned a retry result; `/api/v1/query/regenerate` returned `kind: refine`; see `screenshots/phase1-rerun-06-reject-regenerate.png`. |
| History list/detail/filter behavior works from UI and API. | Pass | History list showed the accepted query with SQL and connection metadata. Detail/filter were not separately exercised in this browser rerun. |
| User-facing strings and component styles remain i18n/RTL-ready. | Skipped | Not meaningfully assessed beyond visible English Phase 1 surfaces in this rerun. |

Task counts: Pass 8, Fail 0, Skipped 2, Blocked 0.

## Browser Flows Actually Completed

| Flow | Status | Evidence |
|---|---|---|
| Open frontend. | Pass | `screenshots/phase1-rerun-01-open-frontend.png` |
| Sign in as local admin through the UI. | Pass | `screenshots/phase1-rerun-02-signed-in.png`; `/api/v1/auth/sign-in` returned 200. |
| Ask one normal natural-language question. | Pass | `screenshots/phase1-rerun-03-normal-question-outcome.png` |
| Verify SQL/result card appears, or record sanitized block. | Pass | SQL/result card rendered `SELECT COUNT(*) FROM customer`, one row with count `599`. |
| Accept/save successful result if available. | Pass | Accept clicked; `/api/v1/query/accept` returned 201. |
| Open History and verify accepted query appears. | Pass | `screenshots/phase1-rerun-05-history-after-accept.png`; history contained the unique smoke question. |
| Exercise reject/regenerate if supported by current UI. | Pass | Reject returned a new result; regenerate returned a refine prompt. |
| Exercise one unsafe/evaluator-blocked path. | Pass | Unsafe prompt returned sanitized `error.hostile_input_blocked`; UI showed only a generic security-policy message. |
| Run one real Gemini smoke if configured and query can submit. | Pass | Backend confirmed Gemini config and the live normal query generated SQL/results. |

## Real LLM Result

Pass. The running backend is configured for real Gemini (`LLM_PROVIDER=gemini`,
Gemini credential present, `LLM_MODEL_NAME=gemini-flash-latest`). The live
browser query:

`How many customers are in the database? smoke 20260703235602`

returned:

`SELECT COUNT(*) FROM customer`

Result shape: one column (`count`), one row (`599`). No provider keys or secrets
were visible in the UI or evidence.

## Evidence Files

- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-1-browser-smoke-report.md`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/phase-1-browser-smoke-evidence.json`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase1-rerun-01-open-frontend.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase1-rerun-02-signed-in.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase1-rerun-03-normal-question-outcome.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase1-rerun-04-accepted-result.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase1-rerun-05-history-after-accept.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase1-rerun-06-reject-regenerate.png`
- `audit/full-regression/runs/phase-6-pre-freeze-2026-07-03/screenshots/phase1-rerun-07-unsafe-path.png`

Playwright trace archives were generated locally for debugging but are not
intended for commit because traces can contain full request payloads.

Prior failed-run evidence remains in the same evidence directories for
historical comparison.

## Commands Run

| Command | Exit | Notes |
|---|---:|---|
| `rtk git status --short --branch` | 0 | Branch `main`; only audit evidence files were dirty. |
| `rtk git rev-parse HEAD` | 0 | `c2184ec7e7c044cb6785093a4f6ad106004e04da`. |
| `rtk docker compose -f docker-compose.dev.yml ps` | 0 | Stack running; backend restarted recently and data services healthy. |
| Backend container LLM env presence check | 0 | Provider/model printed; credential presence only, no secret value. |
| Headless Playwright real-use script | 0 | Completed sign-in, normal query, accept/history, reject/regenerate, and unsafe path. |

## Security and Privacy Notes

No secrets are included in the report. The earlier `/api/v1/auth/login` probe was
not used in this rerun. The unsafe prompt produced a sanitized user-visible
message and a sanitized API error (`error.hostile_input_blocked`) without raw
provider credentials, stack traces, or database internals.

Chunk 1 browser/LLM validation is complete for the requested Phase 1 scope.
Chunk 2 is unblocked by this Chunk 1 rerun.
