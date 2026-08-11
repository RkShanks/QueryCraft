# CHUNK-10 persisted security/resource invariant evidence

Status: local disposable PostgreSQL, API, consumer and foundation proof passed on tested product commit `3b6f90dd938d51bef9e04ba4f5a57afce3335b68`. Authoritative `backend-test` and `frontend-test` are pending.

Starting main: `453875adb54599dd1ba16baa10101af6427588fa`.

## Outcome

`IS-GAP-017` and its dependent `IS-GAP-013` are resolved on the tested branch. Revision 010 adds eleven named PostgreSQL invariants: three nullable quota non-negativity checks, one finite/ranged/ordered detection-threshold check, four source-connection state checks, two identity/provider checks, and one detection-singleton unique index. Matching SQLAlchemy metadata is present for every applicable model.

Revision 010 deliberately does not constrain legacy user roles, permission strings, or audit action types. It never selects an authoritative duplicate, deletes corrupt data, normalizes values, or overwrites an existing detection row.

## Named invariants

| Category | PostgreSQL object | Count |
| --- | --- | ---: |
| Nullable daily query quota | `ck_role_quotas_daily_query_limit_nonnegative` | 1 |
| Nullable daily execution quota | `ck_role_quotas_daily_execution_limit_nonnegative` | 1 |
| Nullable daily export quota | `ck_role_quotas_daily_export_limit_nonnegative` | 1 |
| Detection finite range and strict order | `ck_detection_thresholds_ordered_range` | 1 |
| Source database type | `ck_source_db_connections_database_type_valid` | 1 |
| Source lifecycle state | `ck_source_db_connections_lifecycle_state_valid` | 1 |
| Source health state | `ck_source_db_connections_health_status_valid` | 1 |
| Source schema-introspection state | `ck_source_db_connections_schema_status_valid` | 1 |
| User authentication provider | `ck_users_auth_provider_valid` | 1 |
| SSO protocol | `ck_sso_providers_protocol_valid` | 1 |
| Detection singleton | `uq_detection_threshold_config_singleton` | 1 |

Direct-write proof covered three negative nullable quota dimensions, ten threshold boundary cases, four invalid source-state categories, two invalid identity/provider categories, and a second detection row. The threshold cases included both non-finite categories, both columns, equal order, reversed order, and both range boundaries. All 20 direct writes were rejected by their expected named invariant.

## Preflight, refusal, and repair contract

Revision 010 performs a read-only category/count preflight before taking its write-excluding table locks, then repeats the same read-only preflight while locked. Schema and data mutation begin only after both checks pass.

Six populated refusal categories were proven independently: quota, detection threshold, duplicate detection rows, source state, user provider, and SSO protocol. Every refusal returned the same constant value-safe classification. Before/after snapshots proved all of the following unchanged:

- Alembic revision;
- table and schema fingerprints;
- constraints and indexes;
- row counts; and
- row fingerprints.

An empty detection table is accepted and revision 010 inserts exactly one canonical default row. A non-empty valid table is preserved. Downgrade removes only the ten checks and singleton index; it does not remove application rows or the valid default row.

The operator workflow is documented in [the revision-010 invariant repair runbook](../../../../docs/operations/revision-010-invariant-repair.md). It requires a verified backup, category/count-only diagnosis, an explicit owner-approved transaction, verification, and migration retry. Duplicate detection rows are a hard stop until the owner identifies the authoritative row and approves every disposition; the runbook contains no automatic deletion or newest-row rule.

## Migration and concurrency proof

- Dynamic head is revision 010.
- Fresh `base→head` and populated stepwise cycles passed.
- `009→010→009→010` preserved the valid detection row and restored the expected revision-009 state on downgrade.
- Dynamic head downgraded to supported historical targets and re-upgraded through the existing full migration matrix.
- Schema inventory asserted all ten check names and the singleton index name.
- Eight concurrent real-PostgreSQL initializers started against an empty constrained table. They returned one distinct row identifier and left one row.
- Every disposable database was namespace-validated and destroyed by its fixture.

## Fail-closed consumers and API proof

- Query-time detection uses a read-only required-singleton path. Missing, duplicate, non-finite, out-of-range, or reversed configuration is never repaired during a query.
- Admin GET and PUT use the same read-only validation boundary. Missing, duplicate, and invalid states across both methods produced six sanitized 503 cases and no add/flush repair side effect.
- Valid admin update and audit behavior remained green in the existing integration suite.
- Three corrupt quota dimensions failed closed before cache publication or counter execution. Cache-publication count and counter-attempt count were both zero.
- Corrupt source and SSO provider state used the existing sanitized unavailable behavior; persisted canaries and internal database details were absent from responses.

The API-only live proof populated a disposable revision-009 database with one invalid detection category. Admin GET returned the constant 503 response and left the full database snapshot and Alembic revision unchanged. An explicit single-row operator repair was then applied, revision 010 succeeded, and the same API returned 200. No browser was run.

Evidence records only categories, counts, booleans, status codes, and commit/object identifiers. It retains no persisted values, SQL payloads, constraint failure text, hosts, connection strings, stack traces, or canaries.

## TDD history and review guards

- RED `e940f7300667329aaa55cf6c082dcf6de44d8917` and `f58ab37e9b892d6c0aeda13cc1cca1c1e1d9e097` → GREEN `08b235ec8de7c170ce04e64ddd0eb7911f39ac56`: database invariants, atomic preflight, fail-closed quota/source/provider consumers.
- RED `f7873483610b155b10af0699890163280a0601cc` → GREEN `0ef7b21b3c41af4a3d94d8a91c9e52c23eba96ba`: singleton constraint, concurrent initialization, and read-only detection/admin corruption behavior.
- REFACTOR `17fcea09199ac33a6703f97ff8e0669a49bc0c30`: one symmetric migration constraint inventory and one shared required-singleton read path.
- API/runbook proof `bdb26f5c28adc03ed82030575332ebbde3798eb5`; valid SSO persistence fixture correction `3b6f90dd938d51bef9e04ba4f5a57afce3335b68`.

Test Guard retained behavior-level direct-row, side-effect, API, snapshot, and concurrency assertions and removed one redundant singleton mock test. Clean Code Guard produced the symmetric migration/refactored repository structure and found no unresolved production-code finding. Docs Guard verified the runbook categories, commands, refusal semantics, backup/owner-decision requirements, and the value-safe evidence boundary.

## Gates

- Revision-010 disposable PostgreSQL suite: 30 passed.
- Complete disposable migration cycle/index/schema/concurrency suite: 66 passed.
- Explicit migration drift and historical schema/index regressions: 39 passed.
- Backend unit foundation: 2,490 passed, 14 integration-marked cases deselected; three pre-existing warnings.
- Required quota repository/service/cache and detection repository/admin/runtime/hostile-ordering slice: 155 passed.
- Required connection model/service/API and auth/SSO provider persistence slice: 159 passed.
- Required real-service quota/detection/hostile/auth integration slice: 118 passed, 11 environment-conditioned skips.
- Ruff check: all `src`, all tests, and revision 010 passed.
- Ruff format: 436 files already formatted.
- JSON validation and `git diff --check`: passed.
- Authoritative PR `backend-test` and `frontend-test`: pending.

The full-Alembic lint probe also found 31 pre-existing style findings confined to frozen revisions 001–008 and `alembic/env.py`; those immutable historical files were not edited. Revision 010 passed both Ruff gates explicitly.

## Cleanup and baseline

- Disposable migration databases remaining: 0.
- CHUNK-10-created Compose containers and networks remaining: 0.
- Pre-existing July development volumes deleted: 0.
- Browser artifacts created or retained by CHUNK-10: 0.
- Temporary CHUNK-10 cache removal: pending final evidence validation.
- The 14 protected modified PNGs, seven untracked historical screenshots, and untracked traces directory remain unstaged and untouched from the starting dirty baseline.

CHUNK-11 remains blocked until authoritative backend/frontend CI passes and this branch is squash-merged. Do not start CHUNK-11 from local evidence alone. The machine-readable peer is [chunk-10-data-invariants.json](chunk-10-data-invariants.json).
