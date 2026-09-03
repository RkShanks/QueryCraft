# CHUNK-30 — deployment security policy

Status: **Resolved** for `IS-GAP-010` and `IS-GAP-011` on tested product head `bc0da9cfddbfca36d18f44e72cd5d71537bb5d11`, from starting main `84c04a5eb066e670c4377fa0d4eee43e6a2b02d9` on branch `phase-6/wave-19.30-deployment-policy`.

This evidence is value-safe. It retains statuses, counts, policy values and commit identifiers only. Browser screenshots, videos and traces were disabled for the new CSP proof. No credential, cookie, API body, download body, prompt or SQL value is retained.

## Result

Nginx is the sole owner of the six deployment security headers. The FastAPI backend emits none of them and remains authoritative for endpoint-specific `Cache-Control`. The exact deployed CSP keeps `script-src 'self'` without `unsafe-eval`; frame, content-type, referrer, permissions and HSTS protections use the values documented in `docs/operations/deployment-security-policy.md`. Server-scope `always` directives cover HTML, SPA fallback, hashed assets, proxied API success/error/download responses and Nginx errors exactly once.

HTML and SPA fallback use `Cache-Control: no-store`. Fingerprinted `/assets/` files use `public, max-age=31536000, immutable`. API cache values are not hidden, ignored or replaced: authenticated connection responses and audit downloads retained one upstream `no-store`, and download disposition and session cookies passed through.

`API_DOCUMENTATION_ENABLED` is a validated boolean with a secure `false` default. In the production-like stack, anonymous direct and proxied probes of `/docs`, `/redoc`, `/docs/oauth2-redirect` and `/openapi.json` all returned 404. Explicit development/test enablement returned 200 in the focused ASGI matrix. Disabling those HTTP routes left `app.openapi()`, canonical generation, Schemathesis input and generated-client parity at **65 runtime = 65 canonical = 65 generated application operations**.

QueryCraft now owns the base document title and one route-aware title component covers sign-in, Workspace, history, settings, all six current admin routes, access denied and the still-supported `/ask` route. The 12-route × EN/AR unit matrix, locale changes, links, redirect replacement, reload wiring, and back/forward history passed without raw translation keys or stale titles. No physical-direction CSS was added.

## Strict-CSP response validation prerequisite

The first production-Nginx Chromium RED proof reproduced the current AJV `EvalError` and failed SPA mount under the approved CSP. The authorized in-gap fix keeps `backend/openapi.json` as the single schema source and extends `npm run gen:api` to produce deterministic standalone AJV code:

- 329 operation/status validator entries;
- 99 generated union identifiers with 198 ordered alternative validators;
- the transitive closure of response component schemas for sanitization.

`responseValidation.ts` imports these maps. It constructs no AJV instance, calls no `compile()` or dynamic schema validation, and retains `ClientContractError`, structured-clone failure handling, unknown-field stripping, union selection and the existing timestamp, cursor, counter, pagination, query-shape and nested semantic checks. `ajv` and `ajv-formats` are development dependencies only. Generated-source and built-bundle scans found no `require(`, `new Function`, `eval(`, AJV compiler import or compiler marker.

The final exact production build mounted behind real Nginx with the exact CSP in Chromium for EN at 1440×900 and AR at 375×812. Both cases rendered localized sign-in titles and headings, correct `lang`/`dir` including RTL, and zero unexpected console, page or CSP errors after network idle. The permanent test narrowly recognizes only Chromium's standard failed-resource console line for the expected pre-authentication `/api/v1/auth/me` 401; all other errors fail the proof. No CSP bypass was configured.

The same real stack passed one public SSO-provider API response through runtime validation, then completed local sign-in, authenticated Workspace/history navigation and reload. No LLM or source query was executed.

## TDD history

- Documentation policy: RED `90c2b76` → GREEN `4e43436`.
- Proxy response policy: RED `a5999f4` → GREEN `830e9f6`.
- Localized titles: RED `d0a5411` + wiring RED `a31ff43` → GREEN `b6aab58`.
- Public documentation fallback: RED `6a3e91f` → GREEN `75bc347`.
- Strict CSP: browser RED `5f0d443`, sanitized-evidence refinement `a29d78f`, generation/parity RED `e21b5ff`, response-semantics RED `0c24d49`, dynamic-code RED `ecb1892`, transitive-closure RED `e2730aa` → GREEN `bc0da9c`.

No separate refactor commit was warranted.

## Gates

- Backend documentation/proxy/OpenAPI focused suite: 40 passed.
- Backend service-free foundation: 2,409 passed, 366 skipped, 49 deselected; one existing `AsyncMock` warning and zero failures.
- Ruff check and format: pass; 468 files formatted.
- Canonical OpenAPI generation check: pass.
- Schemathesis canonical OpenAPI 3.1 dry run: 65/65 operations passed deterministic generation and schema loading. The anonymous live response-schema/content/header checks passed; unconfigured SSO login/callback status behavior was not used as CHUNK-30 closure evidence.
- Generated validator/response-contract/client suite: 3 files, 32 tests passed.
- Full frontend Vitest: 106 files, 1,399 tests passed.
- ESLint, TypeScript typecheck, CSS lint and test-harness guard: pass; 44 E2E specs classified.
- Production build: pass, 2,334 modules; existing large-chunk warning only.
- `gen:api` and byte-currentness `gen:api:check`: pass.
- Production Nginx Chromium CSP matrix: 2/2 passed.
- Real public-response and authenticated-route Chromium proof: 2/2 passed.
- Compose validation and exact-container `nginx -t`: pass.
- Direct/proxied HTTP matrix: API success 200, API error 404, download 200, documentation 404×4 at both boundaries; zero direct deployment headers and six exact proxy headers.
- JSON, link, leakage, generated-artifact, runtime-bundle, protected-file and `git diff --check` checks: pass.
- Test Guard, Clean Code Guard, Vercel React review and Docs Guard: pass with no remaining finding.

## Isolation and cleanup

The live proof used an isolated Compose project, dedicated ports, fresh PostgreSQL/Redis volumes, a production frontend image and the exact branch backend. Its allowed origin and insecure-cookie setting were limited to loopback HTTP proof. Production policy and source files were unchanged. All disposable containers, networks, volumes, browser output and temporary scripts were removed after evidence collection.

All 23 protected PNG/screenshot/trace files retain their starting SHA-256 hashes and status; none was staged. Draft PR #336 was not changed. Non-Gemini live smoke remains deferred and `IS-GAP-015` remains Partial, with zero external LLM calls. `CHUNK-31` is unblocked but not started. T-905 and Phase 6 freeze work were not started.

Post-merge accounting is **Resolved 44, Pending 1, Partial 2, Needs Decision 0, Total 47**.
