# CHUNK-19 / IS-GAP-029 + IS-GAP-030 + IS-GAP-039 — interaction and form accessibility

Status: resolved on tested branch `phase-6/wave-19.19-interaction-accessibility` in [#317](https://github.com/RkShanks/QueryCraft/pull/317). Starting synchronized main was `abd51680690714f9ae5b759271056c4873f6743f`, the squash merge of [#316](https://github.com/RkShanks/QueryCraft/pull/316). No backend source, endpoint, canonical OpenAPI document, generated API contract or runtime validation rule changed (`git diff abd5168..HEAD -- backend/` is empty and `gen:api:check` parity holds).

Merge bookkeeping reconciliation carried in this branch: `CHUNK-12`/`IS-GAP-019` was confirmed merged through [#310](https://github.com/RkShanks/QueryCraft/pull/310) at main `58098c05dfc92b7fd22b1096d38229e5c8a66f52`, and `CHUNK-18`/`IS-GAP-041`+`IS-GAP-027`+`IS-GAP-028` through [#316](https://github.com/RkShanks/QueryCraft/pull/316) at main `abd51680690714f9ae5b759271056c4873f6743f`. Historical test evidence in the ledgers is unchanged; only obsolete “merge pending” claims were corrected.

The machine-readable [JSON evidence](chunk-19-interaction-a11y.json) records the same behavior, commits, browser results, gates, cleanup and ledger counts.

## Behavior matrix

| Surface | Verified behavior |
| --- | --- |
| Selector semantics | One trigger button with `aria-haspopup="listbox"`, `aria-expanded` and `aria-controls` opens one `<ul role="listbox">`; options are `<li role="option">` elements with no nested interactive descendants. |
| Open focus | Opening moves DOM focus to the selected option, else the first option; re-opening after a selection focuses the newly selected option. |
| Keyboard model | ArrowUp/ArrowDown move active focus with end clamping; Home/End jump; Enter and Space select the active option, close the popup and restore trigger focus. |
| Escape/Tab | Escape closes without selecting and restores trigger focus; Tab closes without programmatic focus restoration so tab order continues naturally. |
| Typeahead | Printable keys build a locale-aware prefix buffer (500 ms reset) starting after the active option with wrap-around; an unmatchable accumulated buffer falls back to the newest character. |
| Active vs selected | The selected option keeps `aria-selected="true"` plus `database-selector-item-active`; keyboard focus carries a distinct `database-selector-item-focused` class and visible focus ring while `aria-selected` stays untouched. |
| List-change coherence | Connection-list changes while open re-derive the active option (removed focus clamps to selected-or-first), never leave stale `aria-selected`, and keep DOM focus inside remaining options. |
| Auto-select safety | A single connection auto-selects exactly once per unique connection id across parent rerenders, without moving focus or duplicating callbacks. Immutable CHUNK-01 source-selection behavior is unchanged (`onSelect(connectionId)` remains the only contract). |
| Delete dialog | The connection-delete overlay is `role="dialog"` + `aria-modal="true"`, labelled by its title and described by its warning. Focus enters at Cancel (least destructive), Tab/Shift+Tab cycle inside, Escape cancels without mutating and restores focus to the Delete trigger. |
| Destructive pending | While the DELETE is pending both dialog controls disable, Escape is ignored, the dialog holds, and exactly one request exists; completion closes once. Localized error mapping continues to sanitize backend detail. |
| Session controls | Session activation and delete are sibling `<button>` elements — the container no longer carries `role="button"` with a nested button. Activation works by click and Enter/Space; delete stops propagation so it never activates the session; collapsed mode exposes one localized named control. |
| Toast semantics | Admin toasts announce as `role="status"` (success) and `role="alert"` (error); every dismissal control has the localized `common.close` accessible name and removes only its own toast. UndoToast renders as a polite `role="status"` region. |
| Undo timer | The destructive countdown pauses while the toast is hovered or contains keyboard focus and resumes from the remaining duration. Expiry fires exactly one DELETE (idempotent guard), Undo cancels permanently, and all timers clear on unmount so nothing fires late. CHUNK-03 deletion lifecycle (begin/rollback/version suppression) and CHUNK-18 recovery behavior are preserved — their suites pass untouched. |
| SignInForm contract | Blank initial values are authoritative; empty username/password boundaries reject client-side before any request; the first invalid field receives focus with `aria-invalid` plus `aria-describedby` association to the single `role="alert"` message. Editing a field clears its error state. Pending attempts disable submission and duplicate click/Enter submissions collapse into one request. Server rejection surfaces the safe localized invalid-credentials message, retains intent for retry, and success announces a polite localized status. Unmount during a pending attempt suppresses stale settlement. |
| Secret hygiene | The typed password never appears in alert/status text, aria attributes, console output or page content outside the password control itself; masked-sentinel/write-only-secret behavior of edit forms was not modified. |

## TDD commits

| Stage | Commit |
| --- | --- |
| RED selector keyboard model | `146fe5011a39fe69108535d5846c21173b3d9826` |
| GREEN selector keyboard model | `138d7af1253976c1baf12283fa94d0e7969a9fe8` |
| RED dialog/session/toast/timer gaps | `9e2a51673d49802c875c30e6d41ee5714d6466de` |
| GREEN dialog/session/toast/timer contracts | `16b00e62026f1a3ddfe434fb0d873376f1403649` |
| RED SignInForm contract gaps | `1341454dbdf9f39dda8629c08b4674bec20ecef8` |
| GREEN SignInForm form contract | `b3944b12c9330d43cfdc25e830a450e0cbc27e97` |
| REFACTOR derived active option + lint guards | `948eb2950fc92115f14c44d30e53bde60f7858c0` |
| Browser matrix + classification | `a9208714b652f87cd064c7edb67ee58bd841d986` |
| Production-build type fix | `32e8c0de02f1ab105286214afd9dd93fd00fd651` |
| Live round trip + toast setup completion | `21a2fcacc92edd3d37104e406068bb3b1cbf1b40` |

The selector RED command was `cd frontend && npx vitest run src/components/chat/DatabaseSelector.keyboard.test.tsx`: 12 of 13 new cases failed against the click-only implementation (open-focus, arrows, Home/End, Enter/Space, Escape/Tab restore, typeahead, active-vs-selected, list-change coherence, auto-select deduplication) while the outside-click case passed. The IS-GAP-030 RED slice added 13 failing cases across SessionItem nesting (3), ConnectionActions dialog semantics (6), UndoToast timed-status behavior (3 of 4; unmount cleanup already held) and admin toast announcements (1). The IS-GAP-039 RED slice failed 4 of 8 new cases (password null boundary, aria association, field-edit clearing, localized success status) while pinning existing correct behavior.

## Browser evidence

Deterministic Chromium matrix (mocked routes, `page.clock` for timers):

`cd frontend && PLAYWRIGHT_HTML_OUTPUT_DIR=/tmp/opencode/chunk19-report PLAYWRIGHT_OUTPUT_DIR=/tmp/opencode/chunk19-browser npx playwright test chunk_19_interaction_a11y.spec.ts`

- 1440px EN selector: full keyboard/typeahead matrix including open-focus, roving arrows, Home/End clamp, Escape/Tab restoration, two-step typeahead, Enter selection reflected on the trigger, and re-open focus on the selected option — passed.
- 1440px EN sign-in: empty-boundary rejection with first-invalid focus and aria association, field-edit error clearing, real-route 401 with secret kept out of console/DOM text, retry accepted, navigation off `/sign-in`, exactly two sign-in requests across the flow — passed.
- 768px AR dialog: modal semantics, focus entering at Cancel, Shift+Tab/Tab cycling, Escape cancel with trigger-focus restore, pending state disabling both controls while holding Escape with a single captured DELETE, then single completion — passed.
- 375px AR sessions/undo: rail expansion at mobile width, keyboard-reachable destructive control, hover pause past the original deadline, resume-from-remainder expiry firing exactly one DELETE per session, focus pause and blur resume on a second toast, and activation independence (no deletion side effect) — passed.
- Result: 4 passed in 9.7s.

Isolated live round trip against the disposable Compose stack (real FastAPI HTTP, PostgreSQL platform, Redis, migrations; no route mocking, no LLM call, no source query):

`cd frontend && CHUNK19_LIVE_USERNAME=<disposable> CHUNK19_LIVE_PASSWORD=<disposable> E2E_BASE_URL=http://localhost:5173 npx playwright test chunk_19_live_signin.spec.ts`

- Empty submission still rejects client-side without a request; wrong-password POST returns real 401 with neither canary nor credential present in console/page-error streams or rendered body; correct disposable credentials reach the workspace — 1 passed in 2.1s.

## Automated gates

- Focused frontend: 471 tests passed (DatabaseSelector both files, SessionItem, UndoToast, ConnectionActions, AdminConnectionsPage, auth suite, locale coverage).
- Full Vitest: 81 files, 1,181 tests passed in ~18s.
- Focused Playwright mocked matrix: 4 passed in 9.7s; live spec: 1 passed in 2.1s.
- `npm run lint` (ESLint flat v10): clean. `npm run typecheck`: clean. `npm run build`: clean. `npm run lint:css` (stylelint): clean. `npm run gen:api:check`: generated-client parity holds (64=64=64 unchanged). `npm run test:harness`: harness guard passed with 32 classified specs including both new entries. `git diff --check`: clean.
- Backend compatibility subset not required: zero backend changes (verified by empty `git diff --stat` for `backend/`).

## Quality guards and cleanup

Test Guard retained behavior-level assertions (focus ownership, announcement roles, single-shot deletion, resume-from-remainder timing, secret absence channels) instead of implementation mirrors; the pre-existing UndoToast/Sidebar suites still pass unmodified in intent. Clean Code Guard found the effect-state-sync violation during lint and the component was refactored to derive the active option from current connections/selection rather than syncing state in an effect. Vercel React guidance required no memoization beyond the derived-value refactor. Docs Guard reconciled commands, counts, commits and endpoint shapes (admin connections list returns a bare `ConnectionResponse` array) against source and outputs.

Environment quirks discovered:

1. The production Docker build compiles test sources through `tsc -b` project references and caught a test-only callback signature that the local `tsc --noEmit` gate missed → fixed the declaration; suggested skill location: `.agents/skills/FRONTEND_GEMINI.md` quirks table.
2. At viewports ≤768px AppShell auto-collapses the rail on mount, and in-rail interactions around identity transitions can leave it collapsed; the browser suite expands explicitly and uses keyboard activation for hover-revealed controls. Responsive layout assertions remain CHUNK-27 scope.
3. Every networked sign-in attempt intentionally unmounts children through the provider’s auth transition (CHUNK-07), so the full SignInForm settlement matrix is owned by component tests while browser proof covers pre-network boundaries, safe rejection outcome and success navigation.
4. The admin connections list endpoint responds with a bare array, unlike user-facing wrapped lists; fixtures must match generated contracts verbatim.

Cleanup removed the disposable Compose project `qc19` with containers/network/volumes, all temporary Playwright HTML/browser output under `/tmp/opencode`, and `test-results`. The protected baseline remains exactly 14 modified tracked PNGs, seven historical untracked screenshots and existing trace archives; none was staged, regenerated, restored or deleted (`git add -A` was never used).

The three gaps are Resolved on tested branch pending this PR’s CI and squash merge. After reconciling the completed merges of [#310](https://github.com/RkShanks/QueryCraft/pull/310) and [#316](https://github.com/RkShanks/QueryCraft/pull/316), ledger totals after CHUNK-19 are 27 Resolved, 3 Resolved on tested branch, 14 Pending and 3 Needs Decision out of 47.
