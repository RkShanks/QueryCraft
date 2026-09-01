# CHUNK-28 merged-main browser privacy closure

Status: **Resolved** for `IS-GAP-047` on tested closure head `8066a973a13b6cba4f709c66d80d8d1f50454253`, delivered through [#341](https://github.com/RkShanks/QueryCraft/pull/341) from authoritative main `4d4938e136b117851e6cf2dc3078b1b880a941ab` after merged fixes #337–#340.

This report is value-safe. It retains only booleans, counts, categories, statuses, classifications, and commit identifiers. It contains no synthetic value, prompt, credential, cookie, response body, SQL payload, downloaded content, browser profile, screenshot, video, trace, or decrypted application ciphertext.

## Result

The complete merged-main privacy matrix passed **8/8** cases in Playwright Chromium with `--workers=1 --max-failures=1`. Chrome DevTools MCP was unavailable, so Playwright Chromium was the documented fallback. Screenshots, video, and traces were disabled. The provider was a loopback-only deterministic Ollama-compatible endpoint; paid and external LLM invocation count was zero.

- Hostile rejection: EN and AR at 1440px, 768px, and 375px passed 6/6. Every rejection returned sanitized HTTP 400, executed neither provider nor source, rendered the localized alert, cleared the prompt, created no user bubble, and recovered with one same-page benign query.
- Provider boundary: the first intended call failed with sanitized HTTP 502 and zero source execution; reload cleanup passed; retry succeeded without a backend restart. Exact totals were 8 provider calls (1 failed, 7 successful) and 7 source executions (1 joint recovery plus 6 hostile-flow recoveries).
- Audit boundary: search, pagination, failed replacement search, retry, reset, reload, CSV/JSON export, and applied-filter authority passed. Five downloads were inspected and removed. No raw filter value remained.
- Additional failures: injected audit 500, prior-context 422, restricted-user 403, provider 502, and hostile 400 states were sanitized. The restricted 403 body was directly inspected before the permission redirect.
- Identity lifecycle: administrator, audit-authorized replacement, and restricted identities used fresh sessions and profiles. Previous-user history was absent after switching, sign-out succeeded, and final browser state was clean.

## Scanner calibration and channel results

All positive controls were detected before product execution and then removed. External controls covered Redis string/hash/list/set/sorted-set/stream values, nested JSON and base64; PostgreSQL text, nested JSON and base64; and backend logs. Browser controls covered DOM text/attributes/forms, accessibility, React current and alternate fibers, TanStack queries/mutations, Zustand, console/page errors, request URLs, API bodies, Web Storage, IndexedDB, CacheStorage, cookies, window name, history, location, resource timing, downloads, filenames, and object URLs. External and browser preflights were both zero.

Fourteen external scans ran from preflight through the final boundary. Every scan returned `canary observed = false`, `Redis observed = false`, `PostgreSQL observed = false`, and `backend log observed = false`, with zero matches. The final scan covered 31 Redis keys, including 23 attempt-related keys and 8 encrypted attempt states, plus 62 PostgreSQL textual/JSON columns. Ciphertext was not decrypted; encrypted attempt state remained functional through failure, reload, recovery, identity, and sign-out flows.

Browser/API classification remained value-safe:

- Audit lifecycle: 46 API responses — 41×200, 2×204, 1×401, 1×422, 1×500; zero page errors and zero unexpected console errors.
- Joint lifecycle: 42 API responses — 36×200, 2×204, 1×400, 1×401, 1×403, 1×502; zero page errors and zero unexpected console errors.
- Every browser privacy channel recorded `observed = false` after each relevant boundary; final object URL count was zero.

## Gates

- Privacy scanner: 2/2; exact serial Chromium: 8/8.
- Focused frontend: 158/158 across 16 files; full frontend: 1,365/1,365 across 104 files.
- Focused backend: 322 non-detector unit + 23 real-detector unit; integration 77 passed, 1 skipped.
- Backend foundation: 2,681 passed, 44 deselected, one known AsyncMock RuntimeWarning; zero failures.
- Ruff check/format, ESLint, typecheck, production build, CSS lint, API parity, 43-spec harness guard, JSON validation, leakage/secret scan, ledger accounting/link validation, and `git diff --check`: pass. The build emitted only the existing large-chunk warning.
- Test Guard: pass. Clean Code Guard: pass with no product-code delta. Vercel React review: pass with no React product change. Docs Guard: pass.

## Isolation and cleanup

The product matrix began with fresh PostgreSQL/Redis databases, browser profiles, users, roles, sessions, audit state, provider counters, and backend logs. Regression gates used a separate disposable database, Redis DB, and source service.

All disposable processes, containers, networks, volumes, databases, users, sessions, provider state, browser profiles, downloads, logs, build/browser output, and runtime helper files were removed. All 23 protected files retained their starting hashes and status: 14 tracked PNG modifications, seven historical screenshots, and two trace archives. None was staged. `git add -A` was never used. Draft PR #336 remains open and draft at unchanged head `c8737db94dd97916b4bbe3e3ee882321db4c9757`; historical CHUNK-28 branches were untouched.

Ledger accounting is now **Resolved 41, Pending 1, Partial 2, Needs Decision 3, Total 47**. CHUNK-29 is unblocked and explicitly not started.
