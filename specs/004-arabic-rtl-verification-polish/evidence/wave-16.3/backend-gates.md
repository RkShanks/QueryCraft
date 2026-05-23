# Wave 16.3 — Backend Foundation Gates

**Date**: 2026-05-23
**Branch**: `phase-4/wave-16.3-cross-language-smoke`
**Reviewer**: Qwen (Backend Implementer)

Backend code changes were made during Wave 16.3 (schema validation fallback, dialect cleanup, JSON serialization, debug print removal). Backend gates are required per Phase 4 plan.

---

## 1. Unit Tests (`pytest tests/unit/`)

```
$ cd backend && uv run pytest tests/unit/ -q
........................................................................ [ 12%]
........................................................................ [ 24%]
........................................................................ [ 36%]
........................................................................ [ 49%]
........................................................................ [ 61%]
........................................................................ [ 73%]
........................................................................ [ 85%]
........................................................................ [ 98%]
...........                                                              [100%]
587 passed, 1 warning in 3.98s
```

**Status**: ✅ **PASS** — All 587 unit tests pass.

**New tests added during remediation**:
- `test_public_schema_fallback_allowed`: Confirms `public.table` falls back to `table` for PostgreSQL default schema.
- `test_cross_schema_access_blocked`: Confirms `secret_schema.table` is **rejected** even if `table` exists (regression guard).
- `test_generate_sql_mysql_strips_public_schema`: Confirms MySQL dialect strips `public.` prefix.
- `test_generate_sql_tsql_strips_public_schema`: Confirms TSQL dialect strips `public.` prefix.
- `test_generate_sql_postgres_preserves_public_schema`: Confirms PostgreSQL dialect preserves `public.` prefix.
- `test_generate_sql_does_not_strip_compound_public`: Confirms `mypublic.table` is NOT stripped.
- `test_store_attempt_serializes_decimal`: Confirms `Decimal` → `float` in Redis JSON.
- `test_store_attempt_serializes_datetime`: Confirms `datetime`/`date`/`time` → ISO string in Redis JSON.
- `test_custom_json_serializes_decimal` / `test_custom_json_serializes_datetime`: Confirms engine JSON serializer behavior.

---

## 2. Ruff Check (`ruff check src tests`)

```
$ cd backend && uv run ruff check src tests
All checks passed!
```

**Status**: ✅ **PASS**

**Issues fixed during remediation**:
- Import ordering in `attempt_store.py` and `base.py` (imports were mid-file after Gemini changes).
- `SIM118` warning suppressed with `# noqa` for asyncpg Record `.keys()` iteration.
- Unused `_DecimalEncoder` import removed from test file.
- Line-too-long in `test_gemini_adapter.py` (4 lines > 120 cols).

---

## 3. Ruff Format Check (`ruff format --check src tests`)

```
$ cd backend && uv run ruff format --check src tests
231 files already formatted
```

**Status**: ✅ **PASS**

---

## Summary

| Gate | Status |
|------|--------|
| Unit tests (587) | ✅ PASS |
| Ruff check | ✅ PASS |
| Ruff format | ✅ PASS |

**Backend gate evidence**: All gates pass. Wave 16.3 backend changes are clean and safe.
