# Phase 4 - Arabic RTL Polish Regression

Source scope: `specs/004-arabic-rtl-verification-polish/`.

## Scope Summary

Phase 4 verifies and polishes Arabic translations, RTL layout, cross-language
natural-language query behavior, localized errors, accessibility, responsive RTL,
and metadata privacy across all surfaces shipped in Phases 1-3.

## Regression Task Matrix

Use `Status` values `Pending`, `Pass`, `Fail`, or `Skipped`. Fill `Evidence`
with command output paths, screenshot/trace paths, or short notes during the run.

| Task | Status | Evidence |
|---|---|---|
| English and Arabic locale key parity is 100%. | Pending | |
| Arabic mode has no English fallback text or raw i18n keys on shipped surfaces. | Pending | |
| `dir="rtl"` applies and layout mirrors for sign-in, workspace, selector, response cards, history, admin connections, forms, and settings surfaces. | Pending | |
| SQL/code blocks remain LTR while surrounding card chrome is RTL. | Pending | |
| Arabic prompts execute against PostgreSQL Pagila, MySQL Sakila, and MSSQL AdventureWorksLT with dialect-correct SQL evidence. | Pending | |
| Localized validation/errors leak no UUIDs, hostnames, driver strings, stacks, or credentials. | Pending | |
| RTL accessibility names and status announcements are present. | Pending | |
| Mobile RTL at 375px and 768px has no horizontal overflow or unusable controls. | Pending | |

## Backend Commands

```bash
cd backend && rtk uv run pytest tests/unit/test_message_keys.py tests/unit/test_security_privacy_evidence.py tests/unit/test_audit_redaction.py tests/unit/test_audit_redaction_comprehensive.py tests/integration/test_api_query.py tests/integration/test_history_detail_validation.py -x --tb=short
cd backend && rtk uv run pytest tests/unit/source_db tests/unit/evaluator/test_dialect_evaluator.py tests/unit/evaluator/test_dialect_validation.py -x --tb=short
cd backend && rtk uv run ruff check src tests
cd backend && rtk uv run ruff format --check src tests
```

## Frontend Commands

```bash
cd frontend && rtk npm test -- --run i18n
cd frontend && rtk npm test -- --run locales
cd frontend && rtk npm test -- --run no-physical
cd frontend && rtk npm run lint
cd frontend && rtk npm run typecheck
cd frontend && rtk npm run build
cd frontend && rtk npm run lint:css
cd frontend && rtk npm run test:e2e -- i18n-audit.spec.ts rtl-snapshots.spec.ts wave_16_3_smoke.spec.ts
```

## Browser / Manual Smoke Checks

- Arabic sign-in, workspace, database selector, response cards, history list and
  detail, admin connections, add/edit form, test connection, refresh schema,
  disable/enable/delete, and settings/admin surfaces.
- Trigger invalid sign-in, invalid connection, unreachable host, failed schema
  introspection, disabled connection, no-connections, and query failure in
  Arabic.
- Inspect mobile viewports at 375px and 768px for overflow and clipped text.
- Keyboard-tab through Arabic forms and selector to verify usable order and
  accessible names.

## API Checks

- API error responses used by Arabic UI contain stable message keys or sanitized
  localized-safe detail.
- No response body for connection/query/history/admin errors leaks credentials,
  raw UUID fallback, host/port, or raw driver exception.
- History entries for Arabic-prompt queries show friendly metadata.

## Real LLM Smoke

Required for Phase 4-style closure. With real local source DB fixtures running
and provider configured, submit Arabic prompts against:

- PostgreSQL Pagila.
- MySQL Sakila.
- MSSQL AdventureWorksLT.

Capture generated SQL, dialect evidence, execution result, and Arabic/RTL UI
wrapper evidence. If the provider returns English narration, record it as allowed
only when UI wrapper labels are Arabic.

## Expected Pass Criteria

- Locale parity and frontend gates pass.
- Browser smoke finds no English fallback, missing keys, RTL layout breakage, or
  metadata leaks.
- Real Arabic prompt smoke works against all three required source DBs or blocks
  Phase 4-style closure until environment is fixed.

## Known Local Skips / Limitations

- LLM narration language is best-effort; UI chrome must be Arabic.
- Technical database names such as PostgreSQL, MySQL, and MSSQL remain as brand
  strings.
- User-provided connection display names remain as entered.
- Chart axis flipping is out of scope.

## Evidence To Capture

- Locale parity output.
- Structured browser report: route, action, expected, observed,
  console/network errors.
- Screenshots only for failures, ambiguity, or before/after proof.
- Real Arabic prompt SQL/result evidence for all three DBs.

## Update Notes For Future Waves

Every new UI surface from later phases must add Arabic/RTL smoke coverage here
or in its own phase file. Keep the no-metadata-leak checks cross-cutting.
