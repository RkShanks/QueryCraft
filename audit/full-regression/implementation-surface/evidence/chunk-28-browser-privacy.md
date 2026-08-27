# CHUNK-28 browser privacy evidence

Status: **Blocked — product defect reproduced** for `IS-GAP-047`.

This report is value-safe. The synthetic sensitive value was generated in memory only. No literal canary, credential, cookie, prompt, SQL, response body, stack trace, screenshot, trace, browser profile, or downloaded payload is retained here or in the repository.

## Runtime and method

- Browser runner: isolated Playwright Chromium substitution.
- Chrome DevTools MCP: unavailable in this environment (`false` in the JSON summary).
- Runtime: disposable FastAPI backend with disposable PostgreSQL and Redis state, disposable users/sessions/audit rows, and a fresh browser profile.
- The API and browser were exercised together. Runtime containers, network, browser output, and temporary helper files were destroyed after the stop condition.

## RED/GREEN and live result

- RED proof: the value-safe scanner test was run before its helper existed and failed at module resolution.
- GREEN proof: the scanner tests passed after the helper was added (2 tests).
- Live hostile-rejection boundary: the real API returned HTTP 400 with the sanitized `error.hostile_input_blocked` message classification.
- The subsequent value-safe browser scan returned `DOM text contains sensitive value = true`. The run stopped immediately, as required. The captured failure exposed only a boolean classification; the literal value was not printed or retained.

Because a synthetic canary remained in the DOM after a hostile request that returned a sanitized API error, this is a product defect requiring a separate fix. No product code was changed in CHUNK-28, and no closure or Pass claim is made.

## Deferred flows

Provider/dependency failure, audit search/export/download inspection, identity switching/cache isolation, and post-navigation cleanup were not continued after the first observed leak. Their status is `not_run_after_stop` in the JSON evidence. They must be re-run after the separate product fix.

## Cleanup

The backend and frontend processes were stopped. Disposable PostgreSQL and Redis containers and their network were removed. Temporary compose/env/seed files and Playwright output were removed. Protected historical screenshots, traces, and the 14 tracked PNG changes were left untouched and unstaged.

