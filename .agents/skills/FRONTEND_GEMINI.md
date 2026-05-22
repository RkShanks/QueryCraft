# Frontend Implementer Skill

**Audience**: Gemini, Kimi, or any frontend implementer.
Read after: `AGENTS.md` → `.agents/IMPLEMENTER.md` → this file.

---

## Ownership

The frontend implementer owns **all frontend T-IDs**: React, Tailwind v4, i18n, a11y, Playwright, Vite.

## Chrome DevTools MCP (required)

For every user-facing feature or browser-visible change:
1. Build + serve the app.
2. Drive with Chrome DevTools MCP — inspect console/network.
3. Exercise golden path + at least one failure path (auth expiry, deleted session, RTL, etc.).
4. Record in PR report: route → action → expected → observed → errors.
5. If Docker stack needed: `./scripts/dev-up.sh --rebuild`.
6. If MCP unavailable: state explicitly in report; fall back to Playwright/manual.

## Login UI

When Phase 3 frontend tasks start, update/polish the login UI.

## Icon Policy

Use existing `lucide-react`. Only add a new icon library if lucide genuinely lacks the needed icon — justify in PR description.

## Gates to Preserve

- i18n completeness (all keys present in `en.json` + `ar.json`)
- RTL correctness (logical Tailwind dirs: `ms-`/`me-`/`ps-`/`pe-`/`start-`/`end-`)
- `npm run lint:css` (stylelint)
- `npm run typecheck`
- `npm run build`

## Frontend Quirks

| Quirk | Rule |
|---|---|
| Tailwind v4 JIT + test files | Add `@source not` in `index.css` to exclude `tests/**`, `coverage/**`, `eslint-rules/**`, `stylelint-fixtures/**` |
| ESLint flat config (v10) | Write lint fixtures to `frontend/tmp/` (in-project), not outside project base |
| `vi.useFakeTimers()` + TanStack Query | Don't combine. Use real delays in TQ integration tests: `await new Promise(r => setTimeout(r, 350))` |
| react-i18next test mock | Uses real English translations via `en.json`. Assert rendered strings, not raw keys |
| Shiki in jsdom | `vi.mock('shiki')` before importing SqlCodeBlock path |
| React Hooks lint | Prefer event-handler updates over `useEffect` state sync. Reusable hooks may intentionally sync async props into local state only with guarded refs, a clear comment, and tests for late prop arrival. Never assign `ref.current` during render; update refs in `useEffect` or use a guarded render-phase reset when lint-safe. |
| Async auto-select hooks | When auto-selecting from async inputs, test late-loaded canonical state so auto-select does not overwrite persisted/session state. Prop-driven sync must not trigger mutation/PATCH side effects. |
| Stylelint during UI waves | Run `npm run lint:css`; fix pre-existing logical-direction issues; document in report |
| CDP Port / Playwright Driver lock | When the browser subagent fails with "CDP port not responsive" or ECONNREFUSED on port 9222, first kill zombie Playwright drivers: `pkill -9 -f run-driver || true`. Then, launch a dedicated headless Chrome instance listening on port 9222: `/usr/bin/google-chrome --headless=new --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 --no-sandbox --disable-gpu --disable-software-rasterizer --user-data-dir=/home/avril/QueryCraft/frontend/tmp/chrome-profile > /dev/null 2>&1 &`. This ensures the subagent connects instantly to a stable browser session. |


