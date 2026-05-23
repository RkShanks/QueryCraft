# Data Model — Phase 4: Arabic/RTL Verification and Polish

**Created**: 2026-05-23
**Phase**: 4

---

## No New Entities

Phase 4 introduces zero new database tables, columns, migrations, or API contracts. All work operates on existing entities from Phases 1–3:

| Entity | Phase Introduced | Phase 4 Impact |
|--------|-----------------|----------------|
| `en.json` / `ar.json` (i18n locales) | Phase 1/2 | Audit for parity; patch if gaps found |
| CSS stylesheets / Tailwind classes | Phase 1/2/3 | Audit for logical-property compliance; fix if physical directions found |
| UI components (React) | Phase 1/2/3 | Smoke-tested in Arabic/RTL; not redesigned |
| `source_database_connections` | Phase 3 | Used for cross-dialect Arabic prompt smoke; not modified |
| `sessions` / `accepted_queries` | Phase 1 | History metadata verified for Arabic display; not modified |

## Schema Changes

None.

## Migration Changes

None.

## API Contract Changes

None.
