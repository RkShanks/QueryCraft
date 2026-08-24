# CHUNK-23 / IS-GAP-044 + IS-GAP-016 — authentication UX recovery and enterprise IdP evidence

Status: implementation and local verification passed on tested branch `phase-6/wave-19.23-auth-recovery-idp`, starting from synchronized main `12a2d04dee63ed24636ec12bf1a87aa8f970d043`. The machine-readable peer is [chunk-23-auth-idp.json](chunk-23-auth-idp.json). PR, authoritative CI and squash merge remain pending.

No backend endpoint, response contract, or OpenAPI operation changed; runtime/canonical/generated parity remains 64 = 64 = 64 (`gen:api:check` clean, generated tree untouched).

## Frontend outcome (IS-GAP-044)

The sign-in surface now renders four distinct accessible SSO provider states: an announced localized loading status while the provider request is in flight, a sanitized EN/AR fetch-failure alert with an explicit Retry that refetches once per click and recovers to configured buttons, the existing configured-provider buttons (browser-navigation boundaries, `window.location.href`, never fetch mutations), and the existing localized no-provider empty notice. Provider failure never renders the empty message or any transport/IdP detail; the empty notice contains no keys or configuration detail.

Both sign-out surfaces (Sidebar footer, AccessDeniedPage) expose an explicit localized EN/AR Retry inside the truthful failed-sign-out alert. Identity/cache semantics are unchanged and CHUNK-07 is preserved: the boundary discards the sensitive feature cache at sign-out start, never restores it after rejection, and clears identity only after a confirmed successful sign-out. Session expiry remains the distinct sanitized `?error=session_expired` surface.

### Confirmed product defect found and fixed

Against the real isolated stack, a rejected local sign-in showed **no** feedback (`alert_count_after_rejection = 0` in a live probe): the identity boundary's `beginAuthTransition` swaps children for the transition spinner during a pending sign-in, unmounting `SignInForm`; on rejection the remounted form started with empty local state. The fix derives the rejection message and the attempted credentials from the persisted mutation state, so the truthful localized alert stays visible and the attempt stays retryable without re-typing. Password secrecy is unchanged (masked input, never rendered as text, never logged). The CHUNK-19 contract tests and the CHUNK-07 boundary tests pass unchanged.

### Frontend state matrix (assertion-bearing)

| State | Behavior locked by tests |
| --- | --- |
| Provider loading | `role="status"` announced; empty notice and failure absent until settled |
| Provider configured | Buttons render; no raw i18n keys; click is a navigation boundary |
| Provider empty | Localized `SSO is not configured.` notice; distinct from loading/failure |
| Provider fetch failure | Distinct sanitized EN/AR alert + Retry; not the empty message; no transport text |
| Provider retry | Exactly one new request per click; recovers to buttons |
| Invalid callback | Mapped localized message; raw `error`/`code`/`state` values absent from DOM |
| Local blank submit | Client-side rejection before any network access; first invalid field focused |
| Local double submit | One request per attempt; duplicate click/Enter suppressed while pending |
| Local rejection | Truthful alert visible after the identity transition; no secret echo |
| Local success | Permission-aware landing on the permitted route |
| Rejected sign-out | Identity preserved, fresh feature cache, localized alert + Retry |
| Successful sign-out | Identity cleared, public shell rendered, storage free of identity material |
| Session expiry | Distinct `?error=session_expired` sanitized surface |

## Isolated enterprise IdP evidence (IS-GAP-016)

A fully disposable isolated runtime lived only under `/tmp/opencode/chunk23-idp` and was destroyed after proof:

- Dedicated PostgreSQL 16 and Redis 7 containers (separate ports, fresh volumes, `docker rm -f` + volume destruction afterward); migrations applied to head; one disposable role, one group mapping, and two provider rows seeded directly. No development-stack container, `.env`, provider, user, session, or source database was touched.
- A standards-complete mock IdP served real TLS (generated CA + SAN-correct server certificate) with OIDC authorization-code flow (`/authorize`, `/token`, `/.well-known/jwks.json`) and SAML 2.0 HTTP-Redirect/POST bindings (`/saml/metadata`, `/saml/sso` auto-POST to the real ACS), signed assertions (RSA-SHA256, `wantAssertionsSigned`), key/cert rotation controls, per-mode negative claim/assertion generation, and loopback-only control endpoints.
- The isolated backend verified the IdP TLS chain strictly through a process-scoped CA bundle (`SSL_CERT_FILE`); a control backend instance using the default trust store **rejected** the same IdP (`tls_untrusted_store_rejected = true`, sanitized redirect, no cookie), proving verification was active rather than disabled.
- The disposable Chromium trusted exactly one pinned IdP public key (`--ignore-certificate-errors-spki-list`, SAN/hostname checks still active); no blanket certificate-error bypass was used. Node-side probes used `NODE_EXTRA_CA_CERTS` (strict by default, as the initial `UNABLE_TO_VERIFY_LEAF_SIGNATURE` failure confirmed).
- Browser flows were real top-level redirect chains: provider button → backend login route → IdP authorize/SSO → real callback/ACS POST → session cookie → authenticated landing. No callback, token, assertion, cookie, or URL value was ever written to evidence; all records are booleans/counts.

### OIDC rotation and validation matrix

| Probe | Result |
| --- | --- |
| Happy path (real browser redirects) | Landed authenticated on permitted route; one session cookie; workspace rendered |
| Signing-key rotation (new `kid`, JWKS serves new key only) | Next login succeeded with **zero backend restarts** (JWKS is fetched per callback) |
| Token signed by retired key | Sanitized redirect; no session cookie |
| Recovery after rotation | Fresh login succeeded without restart |
| Wrong audience / wrong issuer / expired / wrong nonce | All sanitized redirects; zero session cookies; no raw material in DOM |
| Replayed state+code callback (fresh context) | Sanitized redirect; no new session cookie |
| IdP outage (browser-side, confirmed down) | No session cookie; sign-in surface reachable again afterwards |
| IdP outage during token exchange (code minted, IdP stopped) | Sanitized redirect; `Set-Cookie` absent |
| Recovery after outage | Full flow succeeded without backend restart |

### SAML rotation and validation matrix

| Probe | Result |
| --- | --- |
| Happy path (AuthnRequest redirect → signed assertion auto-POST → ACS) | Landed authenticated; one session cookie |
| Signing-certificate rotation (provider record updated to new cert + metadata swap) | Next login succeeded with **zero backend restarts** |
| Assertion signed by retired certificate | Sanitized redirect; no session cookie |
| Expired assertion / wrong audience | Sanitized redirects; no session cookies; no assertion material in DOM |
| Replayed assertion (same response posted twice) | First authenticated; replay sanitized with no new cookie |

Console diagnostics during authenticated flows contained only the browser's standard `Failed to load resource: 401` resource line from the pre-auth identity probe; the sanitized failure alert was confirmed rendered (`negative_alert_rendered = true`, `negative_alert_contains_raw = false`).

## TDD commits

| Stage | Commit |
| --- | --- |
| RED provider loading/empty/failure/retry matrix | `9eeb142` |
| GREEN localized provider states | `5666173` |
| RED explicit sign-out Retry actions | `e452c6f` |
| GREEN sign-out Retry on both surfaces | `22675f2` |
| RED rejected sign-in visibility (defect reproduction) | `c1b5c02` |
| GREEN persisted-mutation feedback derivation | `51c1e23` |
| Mocked Chromium recovery matrix + classification | `76b7321` |

REFACTOR was not warranted beyond the GREEN corrections; no unrelated code was touched.

## Automated gates

| Gate | Result |
| --- | --- |
| Full frontend Vitest | 1,336 passed (was 1,327 before this wave) |
| Focused frontend suites (SignInPage / SignInForm contracts / Sidebar / AccessDeniedPage / QueryProvider) | all green, including 54 Sidebar+AccessDenied and 32 provider+form cases |
| Mocked Chromium recovery matrix | 7 passed |
| ESLint / typecheck / production build / CSS lint | all clean (existing chunk-size advisory only) |
| Harness guard | passed; 38 specs classified |
| Generated-client parity (`gen:api:check`) | clean; 64 = 64 = 64 |
| Backend OIDC/SAML deterministic suites | 224 SSO + 157 auth unit tests passed |
| Ruff check + format | clean |
| `git diff --check` | clean |

## Browser evidence summary

- Mocked matrix: 7/7 Chromium cases across EN/AR and 1440/768/375 where auth surfaces are affected; DOM, accessibility roles, and storage inspected for raw keys or identity material; unexpected console errors zero in every case.
- Isolated live stack: 19 recorded probe records plus the TLS-strictness negative and the diagnostics probe, all executed against the disposable PostgreSQL/Redis/backend/frontend/IdP runtime under `/tmp`; every failure mode produced a sanitized localized redirect with zero session cookies.

## Cleanup and baseline

- Disposable containers, volumes, IdP/backend/frontend processes and browser outputs under `/tmp/opencode/chunk23-idp` were destroyed; no temporary IdP or browser artifacts remain.
- The protected baseline (14 modified tracked PNGs, seven historical untracked screenshots, trace archives) was not staged, regenerated or deleted; `git add -A` was never used.

Both gaps are Resolved on this branch pending this PR's CI and squash merge. Ledger totals after CHUNK-23 merge will be 38 Resolved, 0 Resolved on tested branch, 6 Pending, 3 Needs Decision out of 47.
