# Quickstart — Phase 6: Quotas, Hostile Input Detection, Audit Hardening

## Prerequisites

- Phase 5 FROZEN on `main` (commit 6ecbcd8)
- PostgreSQL 15, Redis 7 running
- Python 3.12, Node.js 20+
- Backend virtualenv activated (`cd backend && source .venv/bin/activate`)

## Setup

```bash
# 1. Switch to the wave branch per orchestrator dispatch
# Branch is created/assigned by the orchestrator for each wave.
# See "Branch Naming" below for naming convention.
# Example: git checkout -b phase-6/wave-18.0-foundation main

# 2. Run migration
cd backend
alembic upgrade head

# 3. Verify backend
uv run pytest tests/ -x --tb=short
uv run ruff check src/
uv run ruff format --check src/

# 4. Verify frontend
cd ../frontend
npm install
npm test -- --run
npm run lint
npm run typecheck
npm run build
npm run lint:css
```

## Key Files to Create/Modify per Wave

### Wave 18.0 — Foundation
- `backend/alembic/versions/008_phase6_quotas_detection_audit_hardening.py` — new migration
- `backend/src/app/db/models/role_quota.py` — new model
- `backend/src/app/db/models/detection_config.py` — new model
- `backend/src/app/db/models/enums.py` — extend AuditActionType, Permission
- `backend/src/app/schemas/quota.py` — new schemas
- `backend/src/app/schemas/detection.py` — new schemas
- `backend/src/app/schemas/audit_search.py` — new schemas

### Wave 18.1 — Quotas
- `backend/src/app/services/quota_service.py` — new service
- `backend/src/app/repositories/quota_repository.py` — new repository
- `backend/src/app/api/v1/admin_quotas.py` — new router
- `backend/src/app/api/v1/query.py` — modify (add quota check)
- `frontend/src/pages/AdminQuotasPage.tsx` — new page
- `frontend/src/api/quotas.ts` — new API client
- `frontend/src/locales/en.json` — add quota keys
- `frontend/src/locales/ar.json` — add quota keys

### Wave 18.2 — Hostile Input Detection
- `backend/src/app/services/detection/` — new package
- `backend/src/app/services/detection/detector.py` — pipeline service
- `backend/src/app/services/detection/rules/` — 5 built-in rule modules
- `backend/src/app/api/v1/admin_detection.py` — new router
- `backend/src/app/api/v1/query.py` — modify (add detection check)
- `frontend/src/pages/AdminDetectionPage.tsx` — new page or section
- `frontend/src/locales/{en,ar}.json` — add detection keys

### Wave 18.3 — Audit Search/Export
- `backend/src/app/services/audit_search_service.py` — new service
- `backend/src/app/services/audit_export_service.py` — new service
- `backend/src/app/api/v1/admin_audit.py` — extend with search/export endpoints
- `frontend/src/pages/AdminAuditPage.tsx` — extend with search/export UI
- `frontend/src/locales/{en,ar}.json` — add audit search/export keys

## Gate Commands

```bash
# Backend gates
cd backend
uv run pytest tests/ -x --tb=short
uv run ruff check src/
uv run ruff format --check src/
git diff --check

# Frontend gates
cd frontend
npm test -- --run
npm run lint
npm run typecheck
npm run build
npm run lint:css
git diff --check
```

## Branch Naming

```
phase-6/wave-18.0-foundation
phase-6/wave-18.1-quotas
phase-6/wave-18.2-hostile-detection
phase-6/wave-18.3-audit-hardening
phase-6/wave-18.4-verification-closeout
```
