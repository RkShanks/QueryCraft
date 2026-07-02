# Phase 2 - Premium UI and RTL Regression

Source scope: `specs/002-phase2-premium-ui-rtl/`.

## Scope Summary

Phase 2 adds conversational sessions, a premium dark UI shell, response cards,
feedback signals, Arabic/RTL activation, admin LLM context cap settings,
real-provider wire-format contract tests, and lifecycle invariant testing.

## Feature Checklist

- New Chat creates a session, focuses prompt input, and stores preview text.
- Sidebar switches sessions, groups by Today / Previous 7 Days / Older, and
  supports delete with a 5-second undo window.
- Follow-up questions include the last N completed attempts according to admin
  context cap.
- Response card renders highlighted SQL, result table, copy/regenerate actions,
  thumbs feedback, implicit feedback, and saved state.
- Admin settings can read/update LLM context cap in range 0-10.
- Arabic locale sets `dir="rtl"` and mirrors sidebar, bubbles, prompt input,
  forms, icons, and response chrome while SQL code remains LTR.
- LLM wire-format contract tests cover happy path, 429, 5xx, malformed response,
  and oversized schema context.
- Lifecycle invariant framework detects lock, feedback, and session-touch leaks.

## Backend Commands

```bash
cd backend && rtk uv run pytest tests/acceptance/test_session_conversation.py tests/integration/test_sessions.py tests/integration/test_feedback.py tests/integration/test_admin_settings.py tests/integration/test_f011_lock_leak.py tests/contract/test_gemini_contract.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/test_admin_settings_unit.py tests/unit/test_session_repository.py tests/unit/test_session_extension.py tests/unit/test_feedback_router.py tests/unit/llm/test_gemini_adapter.py tests/unit/llm/test_adapter_lifecycle.py -x --tb=short
cd backend && rtk uv run ruff check src tests
cd backend && rtk uv run ruff format --check src tests
```

## Frontend Commands

```bash
cd frontend && rtk npm test -- --run
cd frontend && rtk npm run lint
cd frontend && rtk npm run typecheck
cd frontend && rtk npm run build
cd frontend && rtk npm run lint:css
cd frontend && rtk npm run test:e2e -- rtl-snapshots.spec.ts i18n-audit.spec.ts
```

## Browser / Manual Smoke Checks

- Create two sessions, ask a question in each, switch between them, and verify
  isolated conversation state.
- Delete a session, verify immediate removal, undo within 5 seconds, then repeat
  and let the toast expire.
- Submit a follow-up and verify prior turn context behavior at context cap 0 and
  a non-zero cap.
- Use copy SQL, regenerate, thumbs up, and thumbs down controls.
- Switch English to Arabic and inspect sidebar side, prompt button side, bubble
  alignment, and response card layout.

## API Checks

- Session CRUD/list endpoints used by the sidebar.
- Feedback endpoints and saved/feedback persistence.
- Admin settings read/update for LLM context cap.
- Error responses for invalid context cap and unauthorized admin settings access.

## Real LLM Smoke

Use simulated provider contract tests as the default Phase 2 check. Optional live
smoke may submit one follow-up conversation to the configured provider to verify
history context reaches the prompt path. Capture only prompt metadata and SQL,
not secrets.

## Expected Pass Criteria

- Listed gates pass.
- Existing Phase 1 ask/accept/history behavior still works in the new shell.
- Arabic UI has no missing keys or English fallback on Phase 2 surfaces.
- Lifecycle leak tests pass, and no session/feedback state crosses test
  boundaries unexpectedly.

## Known Local Skips / Limitations

- Real LLM narration language is best-effort; UI labels must localize.
- Dedicated saved queries library and session rename UX are out of Phase 2 scope.
- Full mobile shell is deferred; responsive breakpoints must not break layout.

## Evidence To Capture

- Command logs.
- Screenshots for session sidebar, response card, admin settings, Arabic RTL
  workspace, and delete undo.
- API payload/response examples for context cap and feedback updates.
- LLM contract test output for the five provider wire-format cases.

## Update Notes For Future Waves

Add new session or response-card controls here only if they change the Phase 2
session model. Keep provider contract checks aligned with current adapter files
under `backend/src/app/llm`.
