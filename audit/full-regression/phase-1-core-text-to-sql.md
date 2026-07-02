# Phase 1 - Core Text-to-SQL Regression

Source scope: `specs/001-core-text-to-sql/`.

## Scope Summary

Phase 1 proves the end-to-end text-to-SQL loop: local admin sign-in, submit a
plain-English question, generate SQL through the configured LLM provider,
evaluate read-only PostgreSQL SQL, execute against the source database, render a
result table, accept/reject/regenerate, and persist accepted history only. It
also establishes provider abstraction, i18n keys, and logical CSS foundations.

## Feature Checklist

- Local admin login and session expiry behavior.
- Unauthenticated users redirected away from platform features.
- Question validation: non-empty and maximum length.
- LLM provider selection by config and schema context passed to provider.
- Evaluator blocks empty SQL, write/DDL SQL, unsafe PostgreSQL functions,
  multi-statement SQL, and missing schema objects.
- Read-only source execution, timeout handling, and zero-row result behavior.
- Accept persists accepted query and history; rejected/evaluator-rejected SQL is
  not durable history.
- Reject/regenerate allows one distinct retry and blocks byte-identical retry.
- History list/detail/filter behavior.
- User-facing strings and component styles remain i18n/RTL-ready.

## Backend Commands

Run from repo root:

```bash
cd backend && rtk uv run pytest tests/acceptance tests/integration/test_api_auth.py tests/integration/test_api_query.py tests/integration/test_api_history.py tests/integration/test_accept_only_persistence.py tests/integration/test_regenerate_then_accept.py tests/integration/test_evaluator_gate.py tests/integration/test_us5_provider_switch.py tests/integration/test_us5_reconfigured_provider.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/evaluator tests/unit/llm tests/unit/test_query_service_submit.py tests/unit/test_query_service_accept.py tests/unit/services/test_query_service_reject.py tests/unit/services/test_query_service_regenerate.py tests/unit/test_history_service.py tests/unit/test_schemas_query.py -x --tb=short
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
cd frontend && rtk npm run test:e2e -- us1-sign-in-to-accept.spec.ts us2-reject-autoretry.spec.ts us2-double-reject-refine.spec.ts evaluator-blocks-unsafe-sql.spec.ts history-list-detail.spec.ts provider-switch.spec.ts query-timeout.spec.ts
```

## Browser / Manual Smoke Checks

- Sign in as local admin, submit a valid question, see SQL plus result table,
  accept, then verify the entry appears in History.
- Reject a first answer and verify one regenerated answer appears; reject again
  and verify the refine prompt.
- Trigger unsafe SQL, timeout, zero-row, LLM unavailable, and source DB
  unavailable states with sanitized user-visible errors.
- Verify no hardcoded missing i18n keys or physical-direction layout regressions
  on Phase 1 surfaces.

## API Checks

- `POST /api/v1/auth/login`, protected-route access, and session cookie behavior.
- `POST /api/v1/query/submit`, accept, reject, regenerate, and execute flows.
- `GET /api/v1/history` and `GET /api/v1/history/{id}`.
- Evaluator rejection responses must not execute SQL or write history.

## Real LLM Smoke

Applicable. Run only with explicit approval and real provider credentials. Use
the configured provider in `.env`, preferably Gemini for current project smoke,
and submit a small known Pagila question. Capture the generated SQL, evaluator
outcome, result shape, and absence of leaked provider keys.

## Expected Pass Criteria

- All listed backend and frontend commands complete with exit code 0.
- User can complete sign in to ask to accept to history without regressions.
- Unsafe, rejected, duplicate, timed-out, and empty SQL paths do not persist
  durable history.
- No secrets, stack traces, raw provider credentials, or source DB internals are
  visible in UI/API error responses.

## Known Local Skips / Limitations

- Full backend regression has a known local dev-mode secure-cookie limitation
  noted in Phase 6 orchestration: `test_sign_in_sets_secure_cookie` may fail
  under non-HTTPS local configuration. Do not call the phase green if it fails;
  report it explicitly as local config unless rerun in HTTPS-equivalent config.
- Real LLM smoke requires a configured provider key and may incur provider cost.

## Evidence To Capture

- Command logs with exit codes.
- Screenshots or Playwright traces for sign-in, result card, history detail,
  evaluator rejection, and timeout.
- API response snippets for unsafe SQL and duplicate regenerate paths, redacted
  for tokens and credentials.
- Real LLM smoke prompt, generated SQL, result row count, and provider name only.

## Update Notes For Future Waves

If later phases replace a Phase 1 surface, keep this file focused on the current
shipped equivalent rather than the obsolete route. Add any new invariant that
protects the original ask/evaluate/execute/accept contract.
