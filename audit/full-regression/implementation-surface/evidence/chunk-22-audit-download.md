# CHUNK-22 / IS-GAP-034 — audit download contract

Status: **Resolved on tested branch** `phase-6/wave-19.22-audit-download` at `63cc50d`.

## Product contract

- Applied filter state is the sole export authority; unsent draft changes remain excluded.
- CSV and JSON exports validate media type and server `Content-Disposition` metadata before creating a browser download.
- Invalid or mismatched filename metadata uses the safe UTC fallback; unsafe server names are never used.
- Export cancellation, failed responses, retry recovery and in-flight retry suppression produce zero partial downloads.
- Download resources are removed and object URLs revoked exactly once across success, failure and cancellation paths.
- Long applied-filter chips wrap within the 375px RTL viewport.

## Automated proof

- RED/GREEN sequence: applied-filter contract, filename/media-type contract and page recovery locks, followed by gate corrections.
- Backend focused groups: 97 export/redaction/formula/permission cases, 30 search/redaction cases and 21 OpenAPI canonical cases passed.
- Frontend: 1,327 Vitest tests passed; ESLint, typecheck, build, CSS lint, generated-client parity and harness guard passed.
- Harness classification: 37 Playwright specs classified.
- CHUNK-22 Chromium matrix: 4/4 passed.
- Mocked failure/cancellation matrix: 401, 403, 422, 429 and cancellation each produced zero downloads.

## Live disposable proof

- Isolated Compose project used a fresh platform PostgreSQL database, Redis namespace, FastAPI backend and frontend.
- Browser authentication, audit search and CSV/JSON download events used the real FastAPI stack without API route mocks.
- Stable applied resource filter: 2 browser downloads, 3 filtered rows in each format.
- CSV and JSON server filename contracts passed the strict UTC filename pattern and format extension checks.
- CSV and JSON metadata record counts and SHA-256 checksums independently recomputed successfully.
- Applied filter metadata appeared in both files; sensitive and formula-shaped canaries were absent from both files.
- Browser console/page errors: 0 unexpected errors.
- CHUNK-21 real FastAPI auth/runtime boundary: 2/2 passed.

## Cleanup

- Disposable Compose containers, network and volumes were removed after inspection.
- Temporary downloaded files and the disposable seed script were removed after inspection.
- Protected baseline artifacts were not staged or modified by this chunk.

## Merge state

- Local branch gates are green.
- No pull request, authoritative CI run or merge commit exists yet.
