# QueryCraft — Development Environment Quirks

When working on the QueryCraft repo (Phase 1 text-to-SQL platform), the items below have been hit before by previous sessions. Following them avoids re-discovering known friction.

## Frontend tooling

- **NEVER run `npm install` or `npm ci` from the repo root.** This pollutes the root with a stray `node_modules/` and causes "two different versions of @playwright/test" errors. Always `cd frontend/` first.
- **Playwright browsers persist across PC restarts** because `package.json` has a postinstall hook: `"postinstall": "playwright install chromium"`. After `npm ci` in `frontend/`, browsers auto-install to `~/.cache/ms-playwright/` (WSL-persistent).
- **Playwright OS deps** are usually already present in the standard dev environment. If they're missing on a fresh WSL install, run `sudo npx playwright install --with-deps chromium` (the `--with-deps` flag requires sudo). Without sudo, plain `npx playwright install chromium` still works if OS deps are satisfied.

## Backend tooling

- **Always use `uv sync --extra dev` for dev work.** Plain `uv sync` strips pytest, ruff, and other dev tools (uv defaults to prod-only sync). Symptom: `uv run pytest` fails with "command not found" after a plain `uv sync`.
- **Run pytest from `backend/`**, not the repo root. Use `cd backend && uv run pytest -q -m "not integration"` for the CI-equivalent run. Integration tests require docker stack (postgres-source on 5434, postgres-platform on 5433, redis); they're deselected in CI until T-231 lands.
- **Run ruff from `backend/` too**: `cd backend && uv run ruff check src tests`.

## sqlglot AST quirks

When writing/extending `unsafe_pattern.py` rules:

- Built-in PostgreSQL functions like `current_user()`, `current_schema()`, `current_database()` are parsed as **special AST nodes** (e.g., `exp.CurrentUser`, `exp.CurrentSchema`), NOT as `exp.Anonymous`. A generic `find_all(exp.Anonymous)` loop will MISS them.
- **Always add explicit `find_all(exp.SpecificFunctionNode)` checks** for every special function you want to block, in addition to the generic forbidden-name walker.
- Same lesson applied to quoted identifiers (`"current_user"` parses as `exp.Identifier`, not `exp.Column.name`). Wave 4 G-001 surfaced this pattern; Wave 5 Chunk 5.2 generalized it for T-235.

## Test file layout

- This repo uses **co-located test files** (e.g., `HistoryList.test.tsx` alongside `HistoryList.tsx`), NOT `__tests__/` subdirectories.
- If you find a stray `__tests__/Component.test.tsx`, consolidate its tests into the co-located file and delete the `__tests__/` copy. Wave 5 Chunk 5.4 did this cleanup.

## Git / monorepo hygiene

- Foundation gates checklist (run before any commit/push):
  ```bash
  cd backend && uv run pytest -q -m "not integration" && uv run ruff check src tests && cd ..
  cd frontend && npm run test -- --run && npm run lint && npm run typecheck && npm run build && cd ..
  ```
- After fetching, always `git pull --ff-only` to surface any merge needs explicitly.
- Write scratch files to `<repo>/tmp/` (gitignored), NEVER `~/`.

## Backend tooling / test quirks

- **respx.mock context-manager pattern** (Chunk 6.2). `respx.mock(...)` as a decorator silently fails to register routes when combined with async fixtures. Use `async with respx.mock() as router:`, register routes on the router inside the block, and call the function under test inside the block. Rule of thumb: prefer the context-manager form for httpx mocking; the decorator form has gotchas with async fixtures.
- **get_settings.cache_clear() after env monkeypatch** (Chunk 6.2). Monkeypatching env vars in tests has no effect on the `@lru_cache`'d `get_settings()`. Call `get_settings.cache_clear()` immediately after `monkeypatch.setenv`, before reading settings. Rule of thumb: `get_settings()` is cached; bust the cache or your env mutation is invisible.
- **@hey-api/openapi-ts v0.95.0 silent failure** (Chunk 6.4). `npm run gen:api` returns exit 0 but writes no files. Generated `types.gen.ts` is checked in; only regenerate when OpenAPI schema semantics change, and verify file mtimes after running. Rule of thumb: treat the generator as advisory; verify checked-in types by hand when in doubt.
- **Schemathesis requires OPEN_API_3_1.enable()** (Chunk 6.4). Schemathesis fails with "Open API 3.1.0 is currently not fully supported" after bumping the spec to 3.1.0. In contract test setup, add `schemathesis.experimental.OPEN_API_3_1.enable()` at module top. Rule of thumb: the experimental flag is mandatory when the OpenAPI version moves to 3.1.
- **ruff SIM105 / contextlib.suppress in test files** (Chunk 6.9). ruff fails tests with `SIM105: Use contextlib.suppress(Exception) instead of try-except-pass`. Replace `try: ... except Exception: pass` with `with contextlib.suppress(Exception): ...`. Rule of thumb: never use bare `try/except/pass` in this repo; always use `contextlib.suppress`.

## Frontend tooling / test quirks

- **Tailwind v4 `@source not` for test/fixture exclusion** (Chunk 6.3). Built CSS still contains physical-direction utilities even after fixing source files because Tailwind v4 JIT picks up class-name-shaped strings from test assertion literals. Add `@source not` directives in `frontend/src/index.css` to exclude `tests/**`, `coverage/**`, `eslint-rules/**`, and `stylelint-fixtures/**`. Rule of thumb: when a Tailwind v4 build leaks unexpected utilities, suspect test-file scans first.
- **ESLint flat config (v10) temp-file project-base constraint** (Chunk 6.3). ESLint Node API refuses to lint temp files outside the project base, and flat config globally ignores files under custom directories like `eslint-rules/__fixtures__/`. Write programmatic lint fixtures to `frontend/tmp/` (gitignored but inside the project base). Rule of thumb: in the flat-config era, all programmatic lint must use in-project paths.
- **`vi.useFakeTimers()` conflicts with TanStack Query** (Chunk 6.5). Page-level integration tests that mount TanStack-Query-backed components flake or hang after switching to fake timers. Limit `vi.useFakeTimers()` to pure component unit tests (where TQ is not in the tree). For page/integration tests, use real timer delays: `await new Promise(r => setTimeout(r, 350))`. Rule of thumb: fake timers + TQ = pick one; if TQ is in the tree, use real delays.
- **react-i18next test mock uses real English translations** (Wave 8.1). `frontend/src/test/setup.ts` now resolves keys through `frontend/src/locales/en.json` and interpolates `{{vars}}`; tests that assert i18n output should use rendered English strings, not raw translation keys. If a legacy test expects a raw key, update the assertion to the translated copy or pass an explicit `defaultValue`.

## Universal `/speckit.implement` constraints (applies to every wave)

These constraints apply to EVERY `/speckit.implement T-IDs` dispatch unless explicitly overridden in the dispatch message. Treat them as binding.

- **Single PR per wave.** Do NOT open a separate PR per T-ID. All T-IDs in the dispatched range land in one PR.
- **Branch name**: `phase-<N>/wave-<W.X>-<short-name>` (e.g. `phase-2/wave-8.0-foundation`, `phase-2/wave-8.1-shell`, `phase-2/wave-9-llm-contract`).
- **Commit messages**: every commit references the T-IDs it implements in the body (`Implements T-300, T-301, T-303 — sessions table + Session model + AcceptedQuery extensions`).
- **PR description**: references the T-IDs implemented AND the FR/SC numbers verified by the wave. Pull these from the wave header in `tasks.md` (the `> Verifies:` line).
- **Foundation gates MUST pass before opening the PR**:
  ```bash
  cd backend && uv run pytest -q -m "not integration" && uv run ruff check src tests && uv run ruff format --check
  cd ../frontend && npm run test -- --run && npm run lint && npm run typecheck && npm run build
  ```
- **Governance docs are READ-ONLY** with ONE exception. Do NOT modify `spec.md`, `plan.md`, `data-model.md`, `research.md`, or any file under `contracts/`. These are the speckit audit trail. If you believe one is wrong, STOP and report — do not edit. **Exception:** `tasks.md` may be edited ONLY to toggle `- [ ] T-XXX` → `- [X] T-XXX` on tasks you have just completed. No other changes to `tasks.md` are allowed (no task renames, no description edits, no wave reordering, no new tasks).
- **If a `[NEEDS DECISION]` arises mid-implementation, STOP and report** in the final report's BLOCKED markers section. Never invent a product decision. The orchestrator will run `/speckit.clarify` to lock it.
- **Apply locked Design Decisions verbatim** from `tasks.md` (top of file). For Phase 2 those are: lazy session creation, client-side undo timer, Wave 8.2 boundary for `useQuerySubmit`, lifecycle migration in Wave 10.
- **Use logical Tailwind directions** in any new component (`ms-`, `me-`, `ps-`, `pe-`, `start-`, `end-`, `text-start`, `rounded-ee-`). Physical directions are caught by lint in T-180/T-181 (Phase 1) — extended further by T-365/T-366 in Wave 8.4.

## Wave implementation workflow (per-dispatch lifecycle)

This section is binding for every `/speckit.implement` dispatch. Wave 8.0 surfaced gaps that these rules close. Follow the steps in order.

### Step 0 — Pre-flight: discover resume point

Before touching any code, run these commands and read the output:

```bash
git fetch origin
git checkout main && git pull --ff-only
git branch --show-current
git log --oneline -20
```

Then open `tasks.md` and scan for `[X]` markers within the dispatched T-ID range:

```bash
grep -nE "^- \[[X ]\] T-(3[0-9]{2}|2[0-9]{2})" specs/00*/tasks.md | head -50
```

- If **all** dispatched T-IDs are already `[X]`, STOP and report — work is already done. Confirm the branch + PR exists on origin before reporting.
- If **some** are `[X]` and others `[ ]`, resume from the first `[ ]` task in the range. Never re-implement a task that is already `[X]`.
- If **none** are `[X]`, you are starting fresh.

### Step 1 — Create or check out the wave branch

```bash
git checkout -b phase-<N>/wave-<W.X>-<short-name>   # if first time
# OR
git fetch origin phase-<N>/wave-<W.X>-<short-name>:phase-<N>/wave-<W.X>-<short-name>
git checkout phase-<N>/wave-<W.X>-<short-name>
```

### Step 2 — Implement one task at a time

For each T-ID in the dispatched range, in tasks.md dependency order:

1. **Write failing test(s) first**, then commit:
   ```bash
   git add <test files>
   git commit -m "test(T-XXX): <short description>" -m "<body referencing FR/SC if applicable>"
   ```
2. **Implement the task** so the new tests pass:
   ```bash
   git add <impl files>
   git commit -m "feat(T-XXX): <short description>" -m "Implements T-XXX. <body>."
   ```
   (Use `fix`, `chore`, `docs` as appropriate instead of `feat`.)
3. **Mark the task complete in `tasks.md`** and commit:
   ```bash
   # toggle `- [ ] T-XXX ...` to `- [X] T-XXX ...` in tasks.md (no other edits)
   git add specs/00*/tasks.md
   git commit -m "docs(T-XXX): mark task complete in tasks.md"
   ```

Do NOT batch multiple T-IDs into one commit unless they are truly inseparable (rare — e.g. a single Alembic migration that creates two tables referenced as one logical unit). The default is one task per commit triple (test, impl, mark).

### Step 3 — Signature-change caller sweep (CRITICAL)

When any task changes a public function signature, constructor, protocol, or shared schema, before moving to the next task:

```bash
git grep -n "<symbol_name>(" backend/ frontend/ tests/   # find every caller
```

Update **every** caller (including those you did not edit in the current task) to match the new signature. Run the tests for each updated file. Then commit:

```bash
git commit -m "refactor(T-XXX): update all <symbol> callers for new signature"
```

Wave 8.0 missed this step: `QueryService.__init__` gained two required args but `_get_query_service` in `backend/src/app/api/v1/query.py` was not updated, causing CI failure + runtime crash on `/query/submit`. Run the sweep every signature change without exception.

### Step 4 — Per-sub-wave regression sweep

At the end of each sub-wave (8.0, 8.1, 8.2, 8.3, 8.4), before moving to the next sub-wave OR pushing:

1. Run full foundation gates (see Step 5).
2. Identify every module that imports, references, or extends what you changed (even modules you did not edit). For example, if you changed `QueryService` constructor, identify every test file that imports `QueryService` and every router/factory that constructs one. Run their test files explicitly:
   ```bash
   cd backend && uv run pytest tests/path/test_X.py -v
   ```
3. If any dependent test fails, fix it before pushing. Failure in a dependent module is a silent regression — finding it post-merge is much more expensive.

### Step 5 — Foundation gates (run against the committed tree, paste real output)

Run these commands. The output MUST be pasted verbatim in the Wave Final Report. Do NOT summarize, paraphrase, or fabricate. If you skip a step, the gates report is invalid and the orchestrator will reject the PR.

```bash
cd backend && uv run pytest -q -m "not integration"
cd backend && uv run ruff check src tests
cd backend && uv run ruff format --check src tests
cd ../frontend && npm run test -- --run
cd ../frontend && npm run lint
cd ../frontend && npm run typecheck
cd ../frontend && npm run build
```

If any gate fails, STOP. Fix the code (NOT the test, unless the test is genuinely wrong). Do not push broken code. Do not report "complete" with a failing gate.

### Step 6 — Push after every sub-wave (do not hoard locally)

At the end of every sub-wave:

```bash
git push -u origin phase-<N>/wave-<W.X>-<short-name>
```

Do not wait until the full wave is done — pushing per-sub-wave gives the orchestrator visibility and acts as a remote backup. Wave 8.0 violated this rule (work was completed locally but never pushed; required a recovery dispatch).

### Step 7 — Open the PR before reporting complete

"Complete" is not a local state. Until the PR is open on origin AND CI is green, the work is not done. After step 6:

```bash
gh pr create \
  --title "Phase <N> — Wave <W.X>: <Short Name> (T-XXX..T-YYY)" \
  --base main \
  --head phase-<N>/wave-<W.X>-<short-name> \
  --body "$(cat <<'EOF'
## Summary
...

## T-IDs implemented
...

## FRs / SCs verified
...

## Foundation gates (verbatim)
...

## Self-discovered environment quirks
...

## BLOCKED markers
...
EOF
)"
```

Then wait for CI. If CI fails, fix on the same branch (new commits, never amend) and push again. Only once CI is green is the wave "complete".

### Step 8 — Wave Final Report (after PR is open AND CI is green)

Produce the Wave Final Report (template below). Include the PR URL, the HEAD sha as it appears on origin, the actual gate output (not summarized), and any blockers. Reply to the orchestrator with this report. The orchestrator parses it; deviating breaks downstream automation.

## Security non-negotiables (Constitution I)

- **NEVER put API keys, tokens, or credentials in URL query parameters.** httpx and similar libraries log full URLs at INFO. Always use HTTP headers. (Phase 1 finding F-014 — Gemini API key leaked via `?key=...`.)
- **NEVER log raw request/response bodies that may contain user input or LLM output** without redaction.
- **Long-running services that acquire locks** (Redis `processing_lock:*`, DB row locks) MUST release them in a `try/finally` block on every exit path — success, evaluator rejection, executor timeout, LLM failure. (Phase 1 finding F-011 — lock leak.)
- **Alembic startup drift guard.** The backend refuses to start when `alembic current < head` and emits `migration_drift_detected`. If you add a new migration, ensure `alembic upgrade head` is part of any setup/dev script. (Phase 1 finding F-013.)

## DRAFT audit PR pattern

When dispatched an **audit** task (reproduce a finding without fixing it), open a DRAFT PR titled `DRAFT: Wave <N> audit findings — DO NOT MERGE`. The DRAFT preserves the reproduction tests + findings document as a permanent audit record. The follow-up **fix** dispatch lands on a separate branch, closes the findings, and merges. Phase 1 examples: PR #33 (Wave 6 audit DRAFT), PR #40 (Wave 7 audit DRAFT).

## Wave Final Report Template

At the end of every `/speckit.implement` dispatch, produce a final report in this exact format. The orchestrator parses this; deviating breaks downstream automation.

```
Final report — Wave <N.X> <Short Name>
- Branch: <branch-name>
- HEAD sha: <full 40-char sha>
- PR URL: https://github.com/<owner>/<repo>/pull/<N>

T-IDs implemented
- T-XXX: <one-line summary>
- T-XXX: <one-line summary>
- ... (list every T-ID in the dispatched range; mark any as "deferred" with reason)

FRs / SCs verified
- FR-XXX, FR-XXX, ...
- SC-XXX, SC-XXX, ...

Foundation gates
Backend
  <paste pytest output line: "N passed, M deselected in Xs">
  <paste ruff check output: "All checks passed!" or error count>
  <paste ruff format --check output>
Frontend
  <paste vitest output: "Test Files N passed (N); Tests M passed (M)">
  <paste lint output: "✓" or error count>
  <paste typecheck output: "✓" or error count>
  <paste build output: "built in Xs">

Problems encountered
- <each problem encountered + how it was resolved>
- (or "None")

== Self-discovered environment quirks (durable knowledge candidates) ==
List anything you had to figure out on the fly that wasn't in the prompt and
that a future session would also hit. Format:
  1. <symptom you saw>
     <command/fix that worked>
     <suggested SKILL doc location, if obvious>
(or "None")

BLOCKED markers
- <any [NEEDS DECISION] surfaced, or test you couldn't make pass, or external dependency missing>
- (or "None")
```

The orchestrator rolls "self-discovered quirks" into this SKILL.md so future sessions don't re-discover them. Zero tax on tokens; major payoff on velocity.

## Spec-kit commands available

- `/speckit.constitution`, `/speckit.specify`, `/speckit.clarify`, `/speckit.plan`, `/speckit.tasks`, `/speckit.analyze`, `/speckit.checklist`, `/speckit.implement`.
- NO `/speckit.audit` or `/speckit.review` exists (PR #2043 was closed unmerged). Audit chunks use plain-text prompts to the model.

## Common file paths

- Spec: `specs/001-core-text-to-sql/spec.md`
- Plan: `specs/001-core-text-to-sql/plan.md`
- Tasks: `specs/001-core-text-to-sql/tasks.md`
- Constitution: `specs/001-core-text-to-sql/constitution.md`
- Wave plans: `specs/001-core-text-to-sql/plans/wave-N.md` and `wave-N-snapshot.md`
- OpenAPI contract: `specs/001-core-text-to-sql/contracts/openapi.yaml`
- Audit findings (DRAFT branches never merged): `audit/wave-N/{gemini,opus}-findings.md`

## Docker / local-stack quirks

### Quirk #9 — Docker image staleness after `git pull`

`docker compose restart backend` and `docker compose up -d` do NOT rebuild the backend image; they reuse the cached image. Python source changes from `git pull` are silently ignored. Symptom: operator sees behaviour from an older code revision (e.g. `AttributeError: 'Settings' object has no attribute 'LLM_MODEL_NAME'`). Fix: always run `./scripts/dev-up.sh --rebuild` after a `git pull`. Foundation pytest doesn't catch this because tests run against the live source tree, not the built image.

### Quirk #10 — `.env` staleness after edits

`docker compose restart backend` does NOT re-read `env_file`; the running container retains its env vars from creation time. After editing `.env`, you must `docker compose -f docker-compose.dev.yml up -d --force-recreate backend`. The `dev-up.sh` helper does this automatically.

### Quirk #11 — Alembic migration drift after `git pull`

`git pull` may add new migrations (e.g. wave-6 added migration 003 for `attempt_id`). The Docker image contains the new migration files but **does not auto-run them**. Symptom: opaque 500 errors with `UndefinedColumnError: column "X" does not exist`. As of F-013, the backend now refuses to start when `alembic current < head` and emits a structured `migration_drift_detected` log event. Fix: `docker compose -f docker-compose.dev.yml exec backend alembic upgrade head`, or use `./scripts/dev-up.sh` which runs migrations automatically.
