# CHUNK-06 migration-cycle evidence

Status: local focused gates passed on `2a48ec9b0da9c7abe408cb5248104525f5350604`; authoritative backend/frontend CI passed on `ebbda4783efe35b02a50f486cefefc113bea856a` in [#304](https://github.com/RkShanks/QueryCraft/pull/304).

Starting main: `ef818a0d8fad126f4f2a54487ab78c711716d5f8`.

## Outcome

IS-GAP-009 is resolved on the tested branch. Revision 007 now performs one read-only compatibility preflight before any downgrade mutation and emits one constant operator-actionable refusal classification. It never deletes accounts, installs usable local authentication material, or changes authentication mode. Revision 006 also restores the exact revision-005 `TEXT NOT NULL` unique name contract.

The authoritative migration suite uses one brand-new disposable PostgreSQL database per scenario. It covers 32 database scenarios plus one static import-boundary check. Every target is namespace-validated before migration downgrade or database removal.

## Transition matrix

- Empty stepwise upgrade: `base→001→002→003→004→005→006→007→008→009`.
- Fresh one-command upgrade: `base→head`.
- Populated stepwise downgrade: `009→008→007→006→005→004→003→002→001→base`.
- Stepwise re-upgrade: `base→001→002→003→004→005→006→007→008→009`.
- Populated parent cycles: `base↔001`, `001↔002`, `002↔003`, `003↔004`, `004↔005`, `005↔006`, `006↔007`, `007↔008`, `008↔009`.
- Direct historical upgrades: every revision `001` through `008` upgraded directly to dynamic head.
- Head downgrades: dynamic head downgraded independently to every target `001` through `008`.
- Alembic version was verified after every transition; every supported parent schema fingerprint was restored exactly.

## Revision 007 atomic refusal

- Populated direct `007→006` with one incompatible account: constant refusal; revision, schema, indexes, constraints, and row-state fingerprints unchanged.
- Populated `009→006` with multiple incompatible accounts: the same constant refusal; changes from revisions 009 and 008 rolled back with the revision, schema, indexes, constraints, and row-state fingerprints unchanged.
- The refusal classification contains no identity values, counts, row payloads, or exception trace.
- Populated local-only `007→006`: passed.
- Explicit fixture remediation followed by `009→006`: passed; pre-007 users, source metadata, schema cache, sessions, attempts, accepted history, and result metadata remained coherent where representable.
- Compatible re-upgrade to `009`: passed.

## Schema ledger

Fingerprints contain schema object names, column types, constraints, and indexes only.

| Revision | Tables | Columns | Constraints | Indexes | Schema fingerprint |
| --- | ---: | ---: | ---: | ---: | --- |
| 001 | 5 | 30 | 9 | 3 | `5543d6b6c6f92d5403945d6f730f43cac7ac0ce0c0453250a5fe06e33eba4f0d` |
| 002 | 5 | 30 | 9 | 3 | `5543d6b6c6f92d5403945d6f730f43cac7ac0ce0c0453250a5fe06e33eba4f0d` |
| 003 | 5 | 31 | 9 | 3 | `ced093a7926a4f6cc3d8bd3126f5d86ea1b461cba8b0e37b85a4c4a5bf3ba06f` |
| 004 | 6 | 39 | 12 | 5 | `92ab33d7783bda615758536d8244b6c734dae9e344575fd9a703434cc51201e4` |
| 005 | 6 | 42 | 12 | 5 | `430bd60d98b3d57e58ae4588facfcc728dd77475c080b32c929673996d1e7e4b` |
| 006 | 7 | 57 | 15 | 7 | `dd3c016a75a48f046e0367ab738505fd6f6e6e189619b6ccddb951bc0e137a27` |
| 007 | 13 | 116 | 34 | 17 | `351b1ee7c45a7d342d08e159c4b5a9efabe9c46ed42640fb2c0abe183cf4092e` |
| 008 | 15 | 128 | 39 | 18 | `ef9aa86f9ab0248c54f32ddd9afad821b5cbc62df11472a492d215ea94965515` |
| 009 | 15 | 128 | 39 | 21 | `628fe83bab0b4458d0f9ce3860416ed3fc776d948520fee2332c8ab6845f91c8` |

## Focused gates

- Isolated migration suite: 33 passed.
- Existing migration cycle/index/drift unit subset: 38 passed.
- Existing migration drift integration: 1 passed.
- Auth/RBAC/audit/quota/detection/connection model and repository subset: 71 passed, 31 service-dependent cases skipped; the isolated head-cycle suite independently passed real model/repository smoke.
- Changed Python Ruff check and format check: passed.
- Backend `src`/`tests` Ruff check and format check: passed.
- JSON validation and diff check: passed.

## Cleanup and baseline

- Disposable PostgreSQL databases remaining: 0.
- Disposable containers remaining: 0.
- Disposable volumes remaining: 0.
- Protected tracked PNGs, historical screenshots, and traces: unchanged from the starting dirty baseline.

The machine-readable peer is [chunk-06-migration-cycle.json](chunk-06-migration-cycle.json).
