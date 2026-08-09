# CHUNK-07 UI identity and permission evidence

Status: local focused, full-frontend, mocked-browser and isolated live-browser gates passed on tested product commit `3d2f05a6046ed1bd9f6b2a461fedd2c7f82b10db`; PR and authoritative CI are pending.

Starting main: `9cf46653d190d0b778fa70c709575d9758a3bd1e`.

## Outcome

`IS-GAP-023`, `IS-GAP-025` and `IS-GAP-022` are resolved on the tested branch in the required internal order. Authentication identity, permission fingerprint and feature data now form one fail-closed browser boundary. Routes, navigation, declarative hooks and imperative mutations use the same typed eight-permission catalog and exact backend permission contract.

An authenticated user with no usable permission reaches localized `/access-denied`, can sign out, and starts zero feature requests. `/ask` remains supported and permission-gated; its disposition remains owned by CHUNK-31. The role-detail hydration race remains unchanged and owned by CHUNK-15.

## Identity boundary design

- The outer QueryClient owns only authentication state. A separate feature QueryClient is rotated whenever authenticated identity or the sorted permission fingerprint changes.
- The fingerprint contains user, role and sorted permission identity. Role labels never grant access.
- Sign-in, successful sign-out, failed sign-out recovery, session expiry, cookie identity replacement and permission changes cancel in-flight work, empty feature query/mutation caches and reset identity-scoped Zustand/deletion state before protected children render.
- Locale and collapsed-sidebar preference remain identity-neutral. Active session, hovered session, prompt draft and deletion lifecycle do not.
- A monotonic authentication generation is captured by `/auth/me`. Cancellation uses the public AbortSignal contract, and a response from an expired generation cannot publish data.
- A 401 publishes fail-closed session expiry, disables current-user querying, then cancels and removes the outer `currentUser` data after the observer transition. A disabled observer may retain an empty query shell, but every matching query has `data === undefined` and the cache contains no prior identity or permission value.
- A 403 remains a distinct authorization reconciliation: feature data is withheld, current authorization is refetched once, revoked navigation/data disappear, and the user is not logged out.
- Failed sign-out keeps a localized truthful retry state while using a fresh feature cache; it never restores the discarded sensitive cache.
- Guard redirects preserve only the fixed sanitized `?error=session_expired` code. Arbitrary query values are not carried forward.

## Canonical route, navigation and request matrix

| Permission | Protected routes | Permitted landing | Navigation | Request families enabled |
| --- | --- | --- | --- | --- |
| `query.submit` | `/`, `/ask` | `/` | New chat | sessions, user connections, query/decision/feedback mutations |
| `query.history.view` | `/history` | `/history` | History | history list/detail |
| `admin.connections.manage` | `/settings`, `/admin/connections` | `/admin/connections` | Settings, connections | admin settings, connections and schema |
| `admin.roles.manage` | `/admin/roles` | `/admin/roles` | Roles | roles, role detail/policies, group mappings, schema, quota role discovery |
| `admin.sso.manage` | `/admin/sso` | `/admin/sso` | SSO | SSO provider configuration only |
| `admin.audit.verify` | `/admin/audit` | `/admin/audit` | Audit | audit status, entries, retention, verify and export |
| `admin.quotas.manage` | `/admin/quotas` | `/admin/quotas` | Quotas | quota list/status/mutations; no role discovery without `admin.roles.manage` |
| `admin.security.manage` | `/admin/detection` | `/admin/detection` | Detection | detection configuration |

Landing and wildcard order is `/`, `/history`, `/admin/connections`, `/admin/roles`, `/admin/sso`, `/admin/audit`, `/admin/quotas`, `/admin/detection`. A direct forbidden URL goes to authenticated `/access-denied`; it never selects another privileged route. SSO group-mapping requests require `admin.roles.manage`, independently of `admin.sso.manage`. Legacy `role`, `role_name=admin` and lowercase admin values do not bypass explicit permissions.

## Role editor

- One typed catalog supplies route metadata, navigation and all eight role-editor checkboxes.
- Create and edit independently add/remove every catalog permission, including `admin.quotas.manage` and `admin.security.manage`.
- The browser round trip created a role with all eight permissions, saved it, and reloaded it unchanged.
- Editing removed one known permission while retaining another and preserving an unknown server permission. Unknown permissions were sent back to the server but were not rendered as raw translation keys.
- Disposable permission revoke/grant took effect on the next request, updated navigation/API access and did not introduce active-session revocation.

## TDD and blocker remediation

The original CHUNK-07 history preserves RED/GREEN commits for identity switching, failed and successful sign-out, explicit sign-in, session expiry, 403 reconciliation, the permission catalog, no-permission access denial, sidebar/request gating and the exact browser matrix.

The confirmed outer-cache blocker added these focused commits without amending history:

- RED `a8c33d7031710a4314f103a436a63dfbefc59d82` — retained expired outer identity snapshot.
- RED `0f0b91286c9cd0617d96076b9d13839cab9f94ba` — injected/default clients, duplicate expiry, late settlement and later sign-in.
- GREEN `61d5694e522785245a4585ac0a944d3b0119350d` — generation-safe cancellation and post-transition current-user removal.
- RED `52ab72eb0c811066822d56fcb3d42f907cdc3e2f` — router guard stripped the sanitized expiry query during the live late-auth race.
- GREEN `3d2f05a6046ed1bd9f6b2a461fedd2c7f82b10db` — fail-closed publication plus sanitized guard redirect preservation.

Test Guard accepted the real QueryClient/Zustand assertions and HTTP-boundary MSW usage. Clean Code Guard accepted the small generation/filter helpers, public AbortSignal use, idempotent cleanup and unchanged 403 path.

## Browser evidence

The exact-permission browser matrix used nine isolated personas: eight single-permission personas and one no-permission persona. It covered sign-in landing, direct denial, navigation visibility, request prefixes, failed/successful sign-out, repeated identity switching, late feature settlement, role create/edit/reload, unknown-permission preservation, permission revoke/grant, back/forward/reload, storage, console and page errors. The final focused Chromium rerun passed `1/1` with output confined to `/tmp` and removed afterward.

The final live run used a brand-new persistent Chromium profile, a separately named Docker Compose project, isolated PostgreSQL/Redis volumes and two disposable users/roles with disjoint exact permissions. The server session was expired in isolated Redis while one successful `/auth/me` response was held, then two feature requests returned 401 nearly simultaneously.

Value-safe final live observations:

- final expiry route was `/sign-in?error=session_expired`: true;
- outer `getQueryData(['currentUser'])` was undefined: true;
- matching current-user queries containing data: 0;
- prior identity/role/permission snapshot present in outer cache: false;
- all observed feature QueryClients had zero query and mutation entries in the focused real-client regression: true;
- active session, hover, draft and deletion identity state reset: true;
- identity-neutral sidebar preference preserved: true;
- prior values in DOM, accessibility tree or local/session storage: false;
- prior-value DOM flash after releasing the late auth response: false;
- deliberate duplicate feature 401 responses: 2;
- feature requests after expiry settlement: 0;
- unauthorized responses after expiry settlement: 0;
- unexpected application console errors: 0;
- console errors after settlement and after re-login: 0 and 0;
- page errors: 0;
- clean second sign-in landed on its first permitted `/history` route: true;
- replacement cache data-bearing current-user queries: 1;
- old snapshot after replacement: false;
- exact replacement permission snapshot present: true.

Expected browser resource diagnostics were classified separately: three deliberate 401 resource entries and one canceled held-request resource entry occurred only before lifecycle settlement. No raw identity, history, prompt, SQL, cookie, token, credential, source value or console message was retained.

## Gates

- Focused QueryProvider/AuthGuard/PermissionGuard/App/sign-in/access-denied/sidebar suite: 8 files, 117 tests passed.
- QueryProvider focused file: 19 tests passed, including injected/default QueryClients, duplicate expiry, late auth settlement, failed sign-out and distinct 403 reconciliation.
- Final focused Chromium exact identity/permission matrix: 1 passed.
- Full frontend Vitest, run once after focused gates: 70 files, 927 tests passed.
- ESLint: passed.
- Typecheck: passed.
- Production build: passed; the existing bundle-size advisory remained non-failing.
- CSS lint: passed.
- `git diff --check`: passed.
- Test Guard, Clean Code Guard and Docs Guard: passed.

## Cleanup and baseline

- Disposable users, roles and server sessions remaining: 0; their isolated database/Redis volumes were destroyed.
- Disposable containers, volumes, networks and project images remaining: 0.
- Fresh Chromium profiles, browser output and temporary scripts remaining under `/tmp`: 0.
- CHUNK-07 local service ports remaining: 0.
- Protected tracked PNG changes, historical screenshots and traces: unchanged from the starting dirty baseline and never staged.

CHUNK-08 remains dispatch-gated until this one PR passes authoritative backend/frontend CI and is squash-merged. The machine-readable peer is [chunk-07-ui-identity-permissions.json](chunk-07-ui-identity-permissions.json).
