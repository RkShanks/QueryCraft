# Phase 2 Orchestration Log — Premium UI + RTL + Backend Hardening

**Phase**: 002-phase2-premium-ui-rtl
**Started**: 2026-04-30 (Phase 1 closed, Wave 7 hardening shipped)
**Status**: ACTIVE — speckit artifacts complete, Wave 8.0 ready to dispatch
**Append-only.** Never edit past entries. Only add new ones.

This file is the **source of truth for orchestration decisions and reviews** in Phase 2. When asked "why did we decide X?" or "what's the state of Wave Y?", check this file FIRST before re-reading spec/plan/tasks.

---

## Entry format

Every event in this log uses this template:

```
### YYYY-MM-DD HH:MM — <Event Type> — <Short Title>

**Type**: dispatch | review | audit | clarify | decision | hardening | snapshot
**Actor**: orchestrator (Devin / Codex / Claude / etc.) | user | implementer (Kimi)
**Artifacts**: <PRs, commits, file paths affected>

<freeform body — what happened, what was decided, why, what's next>

---
```

---

## 2026-04-30 — Phase 2 charter locked

**Type**: decision
**Actor**: orchestrator (Devin session 93bfbc2d) + user
**Artifacts**: 8 ADRs locked, ready for `/speckit.specify`

After Phase 1 closed (PR #38) and Wave 7 hardening shipped (PRs #40 DRAFT, #41 fix, #42 polish), user requested a premium dark-mode UI refactor bundled with Constitution VI (Arabic + RTL) activation. Backend hardening (real-LLM smoke harness + lifecycle invariant tests) bundled in as parallel streams.

8 ADRs locked through interactive Q&A:

- ADR-1: Sessions table introduced (migration 004); `accepted_queries` gets `session_id` FK + `saved` + `feedback` columns. Cascade delete on session.
- ADR-2: Session preview text = first user message truncated to 60 chars + ellipsis. No LLM-generated summary.
- ADR-3: Implicit feedback truth table (submits follow-up → +1 on prior + saved=true; Accept → +1 + saved=true; Reject → -1; Regenerate → -1 on old; explicit thumbs match clicked action).
- ADR-4: `saved=true` is a metadata flag on `accepted_queries`. NO separate "Saved Queries Library" page in Phase 2 — deferred to Phase 3.
- ADR-5: LLM context is conversational. Each `submit_question` with a `session_id` loads the last N completed attempts. N is admin-configurable via `app_config['llm_context_cap']`, default 3, range 0..10. Admin endpoints: `GET/PATCH /api/v1/admin/settings`.
- ADR-6: Mobile = desktop-first, "don't break, don't shine" — `lg:` prefixes throughout so layouts don't crash on mobile, but full mobile shell deferred to Phase 4+.
- ADR-7: Syntax highlighter = Shiki, lazy-loaded on SqlCodeBlock with custom QueryCraft theme.
- ADR-8: Optimistic delete with 5-second client-side undo toast. No server-side undo state.

Charter: 3 parallel streams.

- **Stream 2A**: UI refactor + Constitution VI (Waves 8.0..8.4, sequential)
- **Stream 2B**: Real-LLM smoke harness (Wave 9, single PR)
- **Stream 2C**: Lifecycle invariant framework (Wave 10, single PR)
- **Stream 2D**: T-253..T-260 polish drain (folded into other streams)

---

## 2026-04-30 — `/speckit.specify` complete

**Type**: artifact
**Actor**: user (opencode in Antigravity terminal) + orchestrator review
**Artifacts**: `specs/002-phase2-premium-ui-rtl/spec.md` (306 lines, commit 0505db0 base)

Spec generated. 8 ADRs captured verbatim, 7 user stories (US-7..US-13), 27 FRs (FR-031..FR-057), 11 SCs (SC-014..SC-024). Constitution VI ACTIVATED, IV/VII/IX/X DEFERRED. Out-of-scope explicit (Saved Library, mobile shell, SSO, charts, MySQL/MSSQL, multi-user).

Orchestrator review found 3 spec gaps:

1. FR-035 "pending attempts" — unclear handling for in-flight attempts with no SQL yet
2. In-flight session deletion described in Edge Cases but no numbered FR
3. SC-022 "under 90 seconds" — arbitrary, hard to validate objectively

Decision: run `/speckit.clarify` to close gaps at spec stage rather than deferring to plan.

---

## 2026-04-30 — `/speckit.clarify` complete

**Type**: clarify
**Actor**: user + orchestrator
**Artifacts**: `spec.md` updated (commit 0505db0)

3 questions answered:

- **Q1** (FR-035 pending attempts) → **A**: Skip pending; only completed (accepted or rejected) attempts count toward cap N. FR-035 reworded.
- **Q2** (in-flight delete edge case) → **A**: Promote to numbered FR-058. "When the user deletes a session with an in-flight query, the system MUST cancel the in-flight query, optimistically remove the session, and show the undo toast. If the user undoes within 5 seconds, the session is restored but the cancelled query result is permanently lost."
- **Q3** (SC-022 90s) → **A**: Replace with measurable "no UI animation > 300ms". Now testable in Playwright.

Total clarifications log in spec.md = 8 entries (5 from specify + 3 from clarify).

---

## 2026-05-12 — `/speckit.plan` complete

**Type**: artifact
**Actor**: user + orchestrator review
**Artifacts**: `plan.md` (498 lines), `data-model.md` (138 lines), `research.md` (85 lines), `contracts/api-contracts.md` (247 lines). Commits 6d7f30a + 1a9ce19.

Plan generated with 7-wave structure as instructed:

| Wave | Stream | Scope |
|---|---|---|
| 8.0 Foundation | 2A | Backend scaffold (migration 004, 7 new endpoints, prompt builder extension) + frontend scaffold (Tailwind tokens, Zustand, TanStack hooks, i18n). NO visible UI change. |
| 8.1 Shell | 2A | AppShell + Sidebar + SessionList + delete-with-undo + WorkspacePage routing. |
| 8.2 Workspace | 2A | UserBubble + AssistantResponseCard + SqlCodeBlock + ResultTable + PromptInput. Full chat UI. |
| 8.3 Action bars + admin | 2A | CodeBlockActionBar + ResponseFeedbackBar + implicit feedback wiring + Settings page. |
| 8.4 RTL hardening + polish | 2A | Playwright RTL snapshots + Arabic QA pass + T-253..T-260 polish drain + Lighthouse ≥85. |
| 9 Real-LLM contract | 2B | respx-mocked Gemini contract tests (5 scenarios). |
| 10 Lifecycle invariants | 2C | pytest fixture framework for cross-test state leak detection + 3 example invariants + migrate 5 tests. |

Stack choices locked: Zustand (R-001), Shiki (R-002), fontsource (R-003), lucide-react (R-004), respx (R-005), Tailwind v4 `@theme` (R-006), Postgres only — no Redis for sessions (R-007), pure pytest fixtures (R-008).

Orchestrator review: plan is comprehensive. Smart catches by speckit:

- Tailwind v4 `@theme` CSS directive used, NOT JS config (orchestrator's earlier hand-rolled prompt had this wrong — speckit corrected)
- TanStack Query + respx flagged as already-installed deps (no new install)
- Optional weekly real-Gemini-API CI job added to Wave 9

4 task-level decisions surfaced for `/speckit.tasks` to lock:

1. Session creation timing — lazy on first message vs eager on "New Chat" click
2. DELETE undo flow — client-side timer vs server-side undo state
3. Wave 8.1 vs 8.2 boundary for `useQuerySubmit` extension
4. Lifecycle invariant migration — which 5 existing tests

---

## 2026-05-12 — `/speckit.tasks` complete

**Type**: artifact
**Actor**: user + orchestrator review
**Artifacts**: `tasks.md` (302 lines, commit e5e82cc). 81 tasks T-300..T-380, 38 `[P]` parallel-safe markers.

All 4 task-level decisions explicitly locked at top of tasks.md:

1. **Lazy session creation**: First `POST /query/submit` with `session_id=null` creates the session server-side. No empty sessions in sidebar.
2. **Client-side DELETE undo**: 5-second client timer holds the DELETE API call. Undo cancels timer (API never fires). Timer expiry fires DELETE → server cascade-deletes. Server has NO undo state.
3. **`useQuerySubmit` extension belongs to Wave 8.2** (ships with PromptInput + chat rendering), NOT Wave 8.1.
4. **Lifecycle migration**: 5 specific tests opted in — `test_query_service_submit_question`, `test_query_service_reject`, `test_feedback_repository_update`, `test_session_repository_touch` (new W8.0), `test_query_service_submit_with_session` (new W8.0).

T-IDs per wave:

| Wave | T-IDs | Count |
|---|---|---|
| 8.0 | T-300..T-333 | 34 |
| 8.1 | T-334..T-342 | 9 |
| 8.2 | T-343..T-352 | 10 |
| 8.3 | T-353..T-361 | 9 |
| 8.4 | T-362..T-369 | 8 |
| 9 | T-370..T-375 | 6 |
| 10 | T-376..T-380 | 5 |

Phase 1 polish backlog re-mapped: T-253→T-364, T-254→T-365, T-255→T-366, T-256→T-367, T-257→T-312, T-258 OBSOLETE (HistoryPage replaced), T-259→T-305, T-260→T-368.

Dispatch order locked: sequential session-by-session (user runs Kimi in opencode/Antigravity). 8 dispatches total. Wave 10 split into 10.a (framework: T-376/T-377/T-378/T-380) and 10.b (migration: T-379) because T-379 depends on T-316 + T-321 from Wave 8.0.

---

## 2026-05-12 — SKILL.md patched with universal constraints

**Type**: hardening
**Actor**: orchestrator
**Artifacts**: PR #43 (merged), commit 560c9c7. `.devin/skills/querycraft-dev/SKILL.md` expanded from 97 → 159 lines.

New sections added:

- Universal `/speckit.implement` constraints (single PR per wave, branch naming, foundation gates, governance docs read-only, STOP on `[NEEDS DECISION]`, logical Tailwind directions)
- Security non-negotiables (F-011 lock cleanup in try/finally, F-013 alembic startup drift guard, F-014 API keys never in URLs)
- DRAFT audit PR pattern
- Wave Final Report Template (strict format Kimi must produce at end of every `/speckit.implement`)

Net effect: ~30% fewer tokens per dispatch (no constraint block paste needed), parseable final report format.

---

## 2026-05-12 — AGENTS.md expanded as orchestrator playbook

**Type**: hardening
**Actor**: orchestrator
**Artifacts**: this PR (in flight). `AGENTS.md` expanded from 5 → ~250 lines.

Cross-phase, cross-model, cross-account orchestrator playbook codified. Replaces chat-history-only handoff. Future Devin / Codex 5.5 / Claude / Cursor sessions can bootstrap with single prompt: "Continue work on RkShanks/QueryCraft. Read AGENTS.md first."

Same PR initializes this orchestration log + backfills Phase 1 log skeleton + creates `audit/wave-<N>/` directory convention for Phase 2 audits.

---

## Status snapshot — 2026-05-12 (post-AGENTS.md merge)

**Phase 2 speckit artifacts**: COMPLETE
**Implementation status**: NOT STARTED — Wave 8.0 ready to dispatch
**Next dispatch**: `/speckit.implement T-300..T-333` (Wave 8.0 Foundation)
**Active branch on main**: (none — last merge was SKILL.md PR #43)
**Open PRs**: none

**Pending Kimi dispatches in order**:
1. Wave 8.0 Foundation — `/speckit.implement T-300..T-333`
2. Wave 8.1 Shell — `/speckit.implement T-334..T-342`
3. Wave 8.2 Workspace — `/speckit.implement T-343..T-352`
4. Wave 8.3 Action bars + admin — `/speckit.implement T-353..T-361`
5. Wave 8.4 RTL + polish — `/speckit.implement T-362..T-369`
6. **Wave 8 multi-model audit** (Gemini + Opus, after 8.4 merges)
7. Wave 9 Real-LLM contract — `/speckit.implement T-370..T-375`
8. **Wave 9 multi-model audit** (Gemini + Opus, after 9 merges)
9. Wave 10.a Lifecycle framework — `/speckit.implement T-376,T-377,T-378,T-380`
10. Wave 10.b Lifecycle migration — `/speckit.implement T-379`
11. **Wave 10 multi-model audit** (Gemini + Opus, after 10.b merges)
12. Phase 2 close + snapshot

---

<!-- Append new entries below this line. Most recent at the bottom. -->

## 2026-05-12 — Wave 8.0 dispatched + recovery + fix

**Type**: dispatch + review + hardening
**Actor**: user (dispatch via opencode/Antigravity) + implementer (Kimi K2.6) + orchestrator (Devin session 93bfbc2d)
**Artifacts**: PR #45 (open, CI green after fix); branch `phase-2/wave-8.0-foundation` HEAD `a39e3b7`; 10 commits

### Initial dispatch

`/speckit.implement T-300..T-333` (Wave 8.0 Foundation, 34 tasks). All 34 tasks implemented locally by Kimi but **not pushed and no PR opened**. Kimi reported "Wave 8.0 ready for merge" via local report only.

### Recovery dispatch

Orchestrator detected no branch on origin via `git ls-remote`. User dispatched a recovery prompt to Kimi specifying: `git fetch + checkout main + pull --ff-only + checkout -b phase-2/wave-8.0-foundation`, 7 logical-chunk commits with conventional-commits format and T-ID references, foundation gates verbatim output, PR creation with required body sections, and explicit report including PR URL.

Recovery delivered: 8 commits + 1 fix-up commit, PR #45 opened at `phase-2/wave-8.0-foundation` → main.

### Orchestrator review

CI failed on initial push (310 passed + 1 failed in backend-test). Findings posted to PR #45:

- **Critical**: `backend/src/app/api/v1/query.py:_get_query_service` was not updated for new `QueryService.__init__` signature (missing `session_repository` + `db_session`). Real `POST /query/submit` would crash at runtime with `TypeError`.
- **High (workflow)**: Wave Final Report claimed `Backend pytest 311 passed`, but CI showed `310 passed + 1 failed`. Gates were not run against the committed tree.
- **Mid**: `backend/tests/integration/test_f011_lock_leak.py` and `backend/tests/integration/test_evaluator_gate.py` still used the old `QueryService` signature (deselected from CI, so didn't break it, but would break when integration suite runs).
- **Low**: `frontend/src/hooks/__tests__/useSessionsHooks.test.tsx` and `frontend/src/stores/__tests__/uiStore.test.ts` use the `__tests__/` subdir pattern; SKILL.md says co-located. Deferred to follow-up.

### Fix dispatch + result

Orchestrator drafted a targeted fix prompt covering: update `_get_query_service` (Critical), `test_f011_lock_leak.py` (Mid), `test_evaluator_gate.py` (Mid), run gates against committed tree, two clean commits, push, wait for CI green.

Kimi pushed 2 fix commits (`6ee0343` production factory, `a39e3b7` integration tests). HEAD now `a39e3b7c33f783438f60a176fb1efb8d8a4c58b5`. CI green on PR #45 (backend-test PASS, frontend-test PASS).

### Remaining open items (not blocking merge)

- 3 `submit_question(session_id=...)` calls in `test_f011_lock_leak.py` (lines 86, 125, 134) still use the old kwarg name. The kwarg was renamed to `http_session_id` in this wave. These tests are deselected — they won't run until integration suite is wired up (Wave 9). Flagging for cleanup in Wave 9 or via a follow-up commit before then.
- `__tests__/` subdir layout in frontend (2 files) — defer to Wave 8.4 polish or end-of-Wave-8 cleanup.

### SKILL.md hardening (PR #46, merged)

Wave 8.0 surfaced 7 workflow gaps. Orchestrator patched SKILL.md in parallel with the Wave 8.0 fix:

- Pre-flight resume scan (Step 0)
- Commit-per-task triple (Step 2) — test then impl then mark-complete
- Signature-change caller sweep (Step 3, CRITICAL) — cites the Wave 8.0 `_get_query_service` miss explicitly
- Per-sub-wave regression sweep on dependents (Step 4)
- Foundation gate integrity (Step 5) — paste verbatim, never fabricate
- Push after every sub-wave (Step 6)
- PR-before-report rule (Step 7) — "complete" is not a local state
- `tasks.md` checkbox exception to governance-docs-read-only rule

PR #46 merged before Wave 8.0 finalized; Wave 8.1 onward will read the new rules from the start.

### Green-light

Wave 8.0 cleared for merge. CI green, Critical fixed, Mid integration tests updated. Remaining items tracked above for follow-up.

---

## Status snapshot — 2026-05-12 (post-Wave-8.0-recovery)

**Phase 2 speckit artifacts**: COMPLETE
**Implementation status**: Wave 8.0 PR #45 cleared for merge; awaiting user merge
**Active branch on origin**: `phase-2/wave-8.0-foundation` (HEAD `a39e3b7`)
**Open PRs**: PR #45 (Wave 8.0) — cleared for merge

**Wave 8.0 deliverables on disk** (will land on main when #45 merges):
- Migration 004 (sessions table + `accepted_queries` extensions + `llm_context_cap=3` seed)
- Session model + SessionRepository CRUD + AcceptedQueryRepository extensions
- `/sessions`, `/feedback`, `/admin/settings` routers + Pydantic schemas
- `prompt_builder` conversation_history support + `submit_question` lazy session creation + implicit feedback on follow-up
- 6 new backend test files + updates to all existing `QueryService` callers
- Frontend scaffold: zustand, design tokens, TanStack hooks (`useSessions`, `useFeedback`, `useAdminSettings`), 13-icon barrel, ~25 i18n keys (en + ar)
- 2 new frontend test files + MSW handlers

**Next dispatch after #45 merges**: `/speckit.implement T-334..T-342` (Wave 8.1 Shell) — Kimi will follow the new SKILL.md workflow rules (per-task commits, caller sweep, regression sweep, push after sub-wave, PR before reporting complete).

---

<!-- Append new entries below this line. Most recent at the bottom. -->
