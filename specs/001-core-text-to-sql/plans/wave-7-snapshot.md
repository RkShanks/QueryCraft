# Wave 7 — Phase 1 Hardening (Real-LLM Smoke + Polish)

Triggered by: real-LLM smoke testing on a developer workstation surfaced 3 production-grade findings that the Phase 1 audit cycle (Waves 3, 4, 5, 6) missed because foundation tests use a stub LLM and don't observe lock state across multiple submits.

## Chunks

| Chunk | PR | Status | Title |
|---|---|---|---|
| 7.1 — Audit | DRAFT #40 | preserved as historical record | reproduction tests for F-011/F-013/F-014 (RED) |
| 7.2 — Fix | #41 | merged | F-011 lock leak + F-013 migration drift + F-014 Gemini key redaction |
| 7.3 — Polish | this PR | merging | scripts/dev-up.sh + SKILL #9/#10/#11 + README compose workflow |

## Findings

- **F-011 — Lock leak in submit_question (CRITICAL)**: 4 paths where the per-session processing lock was acquired but never released (LLM failure, evaluator rejection, executor timeout, success without follow-up). Fixed via try/finally wrapping. Constitutional invariant Inv 3 preserved.
- **F-013 — Silent migration drift at startup (HIGH)**: backend now refuses to start when `alembic current < head`. Loud failure beats silent corruption.
- **F-014 — Gemini API key leak via httpx INFO logs (HIGH, Constitution I)**: API key moved from URL query param to `x-goog-api-key` header, eliminating the leak at the source.

## Lessons

1. **Real-LLM testing reveals what stub-LLM testing cannot.** Phase 2 should add a real-LLM integration smoke harness (via respx or a recorded-cassette pattern) so future regressions are caught pre-merge.
2. **Lifecycle invariants need cross-call test coverage.** Foundation tests reset Redis between tests; lock-leak bugs are invisible to them. Phase 2 should add cross-call invariant tests where state observed at the end of test N is asserted against expectations at the start of test N+1.
3. **Schema drift needs runtime guards.** Operators forgot to run `alembic upgrade head` after a `git pull`. The startup check is now mandatory.

## Phase 2 carryover

- Real-LLM integration smoke harness (broader than F-014 redaction test)
- Lifecycle invariant cross-call test framework
- Polish backlog T-253..T-260 (still deferred from Wave 6)
