# Wave 7 — Black-Box Audit Findings (Kimi K2.6)

Phase 1 closed (PR #38). This audit run discovered three findings during real-LLM smoke testing on a developer workstation. All findings have RED reproduction tests at HEAD. Fixes are tracked separately in Wave 7.2.

## F-011 — Processing lock leak in submit_question (CRITICAL)

- **Symptom**: After submitting any query, the next submit on the same session is 409'd with "A query is already being processed" for up to 300 seconds (TTL of the lock).
- **Affected paths**: LLM failure (502), evaluator rejection (422), executor timeout (504), and successful submit without subsequent accept/reject/regenerate.
- **Repro**: `backend/tests/integration/test_f011_lock_leak.py` (4 tests, all RED).
- **Why Phase 1 missed it**: foundation tests use stub LLM that never raises, and don't observe lock state across multiple submits in one process.

## F-013 — Silent migration drift at startup (HIGH)

- **Symptom**: Backend starts cleanly when `alembic current < head`. Endpoints that touch new columns produce `UndefinedColumnError` 500s.
- **Hit by user during onboarding**: missed migration 003 → accept/history both 500'd until `alembic upgrade head` was run manually.
- **Repro**: `backend/tests/integration/test_f013_migration_drift.py` (1 test, RED).

## F-014 — Gemini API key leaks via httpx INFO logs (HIGH, Constitution Principle I)

- **Symptom**: Backend emits `HTTP Request: POST https://...?key=AIzaSy...XXXX "HTTP/1.1 200 OK"` at INFO level on every Gemini call.
- **Repro**: `backend/tests/unit/test_f014_log_redaction.py` (1 test, RED).
- **Severity**: leaks live API keys into stdout/log aggregators. Real exposure during Devin testing session.
