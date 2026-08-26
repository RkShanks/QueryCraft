# CHUNK-26 / IS-GAP-040 — detection form boundary evidence

Status: **Resolved (deterministic closure)** on branch `phase-6/wave-19.26-detection-form`, starting from synchronized main `2082f8d3ddc17ddc2c56080c051d9ca503ebc967`. RED `18ec64e` → GREEN `59b5be4` → browser proof `06b00e3`. No backend persisted invariant from CHUNK-10 changed; no provider configuration changed; no generated API artifact regenerated (parity gate green, 64=64=64).

## Gap closed

FE detection handler now enforces explicit finite `[0,1]` numeric validation and strict `flag < block` ordering before any mutation, fails closed on malformed responses (CHUNK-17 validators retained as authoritative), preserves valid edits after rejected/failed saves, and exposes deterministic reset/dirty/retry/duplicate-suppression behavior. Backend `DetectionThresholdUpdate` invariants are untouched and remain authoritative.

## Boundary classifications (component/API matrix)

| Classification | Component result | Mutation requests |
| --- | --- | --- |
| Non-numeric text (NaN class) | Blocked, localized range error | 0 |
| Non-finite positive magnitude | Blocked, localized range error | 0 |
| Non-finite negative magnitude | Blocked, localized range error | 0 |
| Below-range value | Blocked, localized range error | 0 |
| Above-range value | Blocked, localized range error | 0 |
| Equal thresholds | Blocked, localized order error | 0 |
| Inverted thresholds | Blocked, localized order error | 0 |
| Direct DOM property bypass | Blocked before handler dispatch to API | 0 |
| Exact valid boundaries (0 and 1) | Accepted, exact payload persisted | exactly 1 |
| Native browser bypass (badInput/range constraint) | Blocked by native constraint validation before submit | 0 |

Pure validator unit matrix: 7 tests covering decimal/exponent parsing, whitespace rejection, non-coercion of non-numeric text, non-finite magnitudes, range-before-order precedence, equal and inverted ordering, and both exact boundaries.

## Mutation request counts (browser, mocked Chromium)

- Invalid bypass matrix: 4 classifications x 3 viewports = 12 blocked submissions, **0 PUT requests** at 1440px, 768px, 375px.
- Keyboard edit + Enter submit with ordering violation: **0 PUT requests** at all three viewports.
- Reset after dirty edit: **0 PUT requests** at all three viewports; authoritative values restored, error state cleared.
- Valid boundary save: **exactly 1 PUT** with the exact ordered payload; success announced once.
- Sanitized server rejection then retry: **exactly 2 PUTs** (first rejected, second succeeds); edits preserved between attempts.
- Arabic boundary rejection: **0 PUT requests**; native-blocked and client-blocked classes both proven under RTL.

## Accessibility and localization pass counts

- `aria-invalid` + `aria-describedby` association to a `role="alert"` message: 3/3 viewports (EN) + Arabic RTL case.
- Localized range and order error messages: EN and AR both asserted (component + browser).
- Success announced via `role="status"` toast: 2 cases (boundary save, retry after rejection).
- Failure announced via sanitized `role="alert"` toast: 2 cases (malformed save response, server 422); no raw backend error text or contract codes in DOM.
- Pending save announced via polite `role="status"`: duplicate-suppression case.
- Keyboard editing and Enter submit: 3/3 viewports; existing Tab-focus/LTR-number regression spec still green.
- RTL: `dir="rtl"` asserted; logical Tailwind classes only; no physical-direction CSS; no raw translation keys (i18n lint clean).

## Regression and gates

- Focused frontend suites: 29 passed (22 page + 7 validator) inside the full 1,358-test Vitest run (102 files, 0 failures).
- Backend detection regression subset: 34 passed (config repo, admin corruption, error sanitization, fail-closed); Ruff clean.
- ESLint, TypeScript, production build, CSS lint, i18n lint, harness guard (39 specs classified), generated-API parity: all green.
- `git diff --check`: clean.
- Browser proof: 12/12 mocked Chromium cases passed (temporary output only; no screenshot baseline updated).

## Cleanup

`test-results/` and temporary browser output removed. Protected dirty baseline (historical PNGs and pre-freeze screenshots) untouched and unstaged. No disposable backend resources were required (mocked browser proof; backend subset read-only). Evidence contains classifications and counts only — no credentials, tokens, raw payloads, raw backend errors, or hostile canary values.

## Residue

None for IS-GAP-040. Separate observation (outside this chunk, reported for triage): the pre-existing XP-008 browser spec's sessions mock uses a glob that does not match query strings, so that spec runs with an unmocked sessions 502; it does not affect its assertions but was fixed only in this chunk's new spec.
