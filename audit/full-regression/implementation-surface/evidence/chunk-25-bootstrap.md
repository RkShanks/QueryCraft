# CHUNK-25 — bootstrap and source-fixture operations

**Gap:** IS-GAP-018 · **Chunk:** CHUNK-25 · **Status: Partial**

Executed from synchronized `main` at `3f86ada49ec97cdf8eb91f32d29d296d5a1763f7` on branch `phase-6/wave-19.25-bootstrap-hardening` (Backend Implementer). TDD triples: RED `45c810e` → GREEN `43186d5` (setup), RED `e09c17b` → GREEN `ec4f9d0` (restore), RED `d9fdbd0` → GREEN `1dcb3cb` (seed), harness tightening `7c0e194`, operational docs `c27b729`. See the [JSON evidence](chunk-25-bootstrap.json).

## What was hardened

### Fixture downloads (`scripts/setup-source-dbs.sh`)

Downloads now use HTTPS only with fail-aware curl flags (`-f`, retries, `--proto '=https'`). Every fixture must match a SHA-256 checksum **before** extraction or installation; mismatches are rejected with a nonzero exit and zero mutation of fixture paths. All temporary state lives under one `mktemp -d` workspace removed by an `EXIT/INT/TERM` trap, so failed downloads, corrupt archives, checksum rejections and interrupted runs leave no artifacts. Reruns are deterministic: present-and-complete fixtures skip downloads; partially installed state is repaired by a fresh verified download.

Checksum provenance is deliberately **not** fabricated by this repository: upstream publishes no vendor checksum for `AdventureWorksLT2022.bak` (GitHub release API digest is null) or `sakila-db.tar.gz`. The script therefore requires an operator-supplied checksum file (`SOURCE_FIXTURE_CHECKSUMS`, default `scripts/fixtures.sha256`; template and derivation steps in `scripts/fixtures.sha256.example`) and fails closed before any network access without it. End-to-end vendor-authority proof remains Setup-dependent.

### MSSQL restore (`scripts/restore-mssql.sh`)

`MSSQL_USER` is allowlisted to `[A-Za-z][A-Za-z0-9_]*` because SQL Server identifiers cannot be parameters; passwords are embedded only as doubled-single-quote `N'...'` literals; control characters in any credential value are rejected before any container command runs. Value precedence is explicit environment > `.env` > documented default, with no assignment clobbering inherited values. The health-wait loop exits nonzero with a constant sanitized message on timeout. Restore behavior is state-aware and idempotent: an ONLINE database skips restore entirely, a non-online database left by an interrupted/partial restore is dropped and restored again exactly once, and a failed restore aborts before login configuration. No secret value reaches stdout/stderr.

### Seed operations (`backend/src/seed_e2e_connection.py`, `backend/scripts/seed_test_user.py`)

The MSSQL restore DSN can no longer be injected through metacharacters: hosts are allowlisted, DSN separators (`;`) and control characters in bound values are rejected before any connection attempt. Connection failures raise one typed sanitized error — the raw driver exception, its DSN and the SA secret never escape (cause preserved internally). Restore planning is extracted into a pure action matrix (`None→restore`, `ONLINE→none`, otherwise `drop+restore`) preserving prior recovery semantics while making partial-failure reruns unit-provable. `seed_test_user.py` now disposes its engine on every exit path including the early no-op.

## Proof summary (disposable harnesses, no shared state touched)

| Category | Cases | Result / exit classification |
| --- | --- | --- |
| Failed download | 2 | nonzero, sanitized, no artifacts, temp cleaned |
| Corrupt archive | 1 | nonzero, nothing installed, temp cleaned |
| Checksum mismatch before mutation | 1 | nonzero pre-extraction/pre-install |
| Checksum required fail-closed | 2 | nonzero before any network access |
| Interrupted setup cleanup | 1 | SIGTERM → nonzero, zero leftovers |
| Rerun after partial failure | 2 | second run completes all fixtures |
| Idempotent rerun | 1 | zero new downloads |
| HTTPS-only fail-aware transport | 1 | both invocations compliant |
| Hostile environment values | 4 | rejected before any exec/SQL |
| Password literal escaping | 1 | doubled-quote literal only |
| Partial MSSQL restore recovery | 1 | DROP then RESTORE exactly once |
| Online rerun skips restore | 1 | zero mutations, role configured |
| Failed restore aborts login config | 1 | login batch never sent |
| Sanitized diagnostics / no secrets | 3 | canaries absent from output and errors |
| DSN/control-character rejection | 3 | rejected before connect |
| Raw driver error sanitization | 1 | typed error, DSN and secret absent |
| Restore action planning matrix | 4 | exact state mappings |
| Seed engine disposal | 2 | dispose on both exit paths |

New cases: 30 (focused suites total 40 including pre-existing regression coverage).

## Gates

Authoritative backend/frontend CI passed in run `32905156993` on `45157a1a65296ebf650df88f26a8e565e0480a2e`.

- Focused script/seed suites: 40 passed (`test_setup_source_dbs_script.py` 11, `test_restore_mssql_script.py` 10, `test_seed_e2e_connection.py` 11, `test_seed_test_user_script.py` 2)
- Required regressions: `test_dev_up_script.py` 4 passed (CHUNK-13 ordering/readiness intact), `test_compose_readiness.py` 2 passed
- Full backend unit foundation: 2289 passed, 365 skipped (integration deselected)
- Ruff check + format check (changed Python): clean
- Shell syntax checks (`bash -n` on all three scripts): clean (shellcheck unavailable locally)
- Compose configuration validation (`docker compose config -q`): passed
- `git diff --check`: clean
- Frontend gates: not required (no frontend changes)

## Isolation and cleanup

All executions used temporary directories under the pytest tmp tree with fake boundary executables; zero disposable containers/volumes were created; the shared development databases were never reset; the protected dirty baseline (pre-existing modified PNGs and untracked screenshots) was untouched; all temporary workspaces were removed automatically by harness teardown. No credentials, environment values, raw SQL, source rows or raw database errors are recorded in this evidence.

## Why Partial

Deterministic closure is complete for failed/corrupt download handling, checksum-mismatch rejection, hostile-input rejection, partial-restore recovery, rerun/idempotency, interrupt cleanup and sanitized diagnostics. The remaining residue is upstream-authority: neither vendor publishes a checksum for these two sample fixtures, so end-to-end vendor-anchored supply-chain verification cannot be proven from here and is classified **Setup-dependent** (per gap isolation rules — no checksums were invented). Closing it requires either vendor-published digests or an owner-approved pinned-checksum policy.
