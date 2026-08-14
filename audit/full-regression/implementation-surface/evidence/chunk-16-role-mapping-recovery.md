# CHUNK-16 / IS-GAP-036 — atomic role and mapping recovery

Status: implementation, local verification, and authoritative CI passed on `phase-6/wave-19.16-role-mapping-transaction`; [PR #314](https://github.com/RkShanks/QueryCraft/pull/314) is open and squash merge is pending. Tested product commit: `bbb7d3421a07eb04c0866acc47a87fa6c6e9f1a2`. Authoritative backend/frontend CI passed on `d14831e1016441d07d6736a3132e9309f78716d2` in run `31766725883`. Starting main: `c92255de4e0be0fde59b3f0bf3045b7115de7354`, the squash merge of [PR #313](https://github.com/RkShanks/QueryCraft/pull/313).

## Outcome

`IS-GAP-036` is resolved on the tested branch. Existing `POST /api/v1/admin/roles` and `PUT /api/v1/admin/roles/{id}` now own one platform-PostgreSQL transaction for role fields, connection policies, requested group mappings and their success audits. No endpoint was added; runtime OpenAPI, canonical OpenAPI and the generated SDK remain **64 = 64 = 64** operations across 48 paths.

The standalone group-mapping endpoints remain available for compatibility. Composite frontend Save no longer calls them: each logical Save emits one role POST or PUT with `group_mappings` in the typed body.

## Transaction contract

| Case | Persisted result | Response/audit result |
| --- | --- | --- |
| Create with role, policies and mappings | All commit together | Authoritative role detail contains mapping IDs/values and policy IDs. |
| Update with unchanged, added and removed mappings | Unchanged rows retain IDs; additions/deletions apply in the same transaction | One `role.mapping.change` event per actual add/remove; no event for unchanged mappings. |
| Omitted update mappings/policies | Existing collections are preserved | Authoritative detail returns the preserved collections. |
| Explicit empty mapping list | All mappings are deleted atomically | Exactly one mapping-delete audit per deleted row. |
| Duplicate values in one body | Nothing is written | Sanitized 422; submitted group value is absent from the response. |
| Group claimed by another role | Nothing in the composite mutation survives | Sanitized 409; submitted group value is absent from the response. |
| Mapping-audit, flush/response-preparation or commit fault | Nothing survives | Sanitized 500; audit and data rows roll back together. |
| Two concurrent claims for one group | Exactly one complete role/mapping winner | Statuses are one 201 and one sanitized 409; winner contributes one role-create and one mapping audit. |

PostgreSQL `INSERT ... ON CONFLICT DO NOTHING RETURNING` makes the unique group claim the concurrency authority. The endpoint prepares and refreshes the response before its only commit, so no fallible response-preparation step can return a declared 500 after commit. Audit writes share the same `AsyncSession`; audit failure fails closed.

Permission remains exactly `admin.roles.manage`. The focused permission gate covers the role and retained standalone mapping routes; legacy role-name strings do not grant access. Error bodies use allowlisted error/message keys and do not echo SSO claims, constraints, SQL, UUIDs, driver details or stacks.

## Audit-count matrix

| Mutation | `role.create` | `role.update` | `role.mapping.change` |
| --- | ---: | ---: | ---: |
| Successful create with two mappings | 1 | 0 | 2 |
| Mapping-only update removing one and adding one | 0 | 0 | 2 |
| No-op mapping update | 0 | 0 | 0 |
| Explicit clear of two mappings | 0 | 0 | 2 |
| Policy-only update | 0 | 1 with `updated_fields=["connection_policies"]` | 0 |
| Conflict, duplicate, audit fault, response-preparation fault or commit fault | 0 net | 0 net | 0 net |
| Concurrent same-group pair | 1 net | 0 | 1 net |

## Client recovery contract

Normal success uses the authoritative role-detail response. After a definite HTTP rejection, the hook refetches and publishes authoritative detail/list state while the editor preserves its draft. After a fetch-level lost response:

- matching authoritative detail resolves as recovered committed success;
- a successful refetch that does not match remains an explicitly uncertain state with the draft preserved;
- a failed reconciliation read uses separate localized copy and does not claim that authoritative state was refreshed;
- create recovery takes an authoritative preflight role-ID snapshot, so stale cache cannot make an older same-shaped role look like this request's commit.

The editor uses an event-time ref lock, so click plus Enter cannot enqueue a second request before React renders the pending state. Pending, rejected, uncertain-with-refresh, uncertain-without-refresh, retry and success states are localized in English and Arabic and exposed through status/alert live regions. Cancel clears the draft; reopening reads the published authoritative cache.

## TDD history

| Slice | RED | GREEN |
| --- | --- | --- |
| Composite create rollback | `880ecaffeab3972e9580b0198dd0789590b80f6b` | `4151810ef06e1aa1256a1bab64848710c558230f` |
| Composite update rollback/diff | `45c7eb58de71d30431626784811fec3f1409d93a` | `83298a7fc034e8835d4d738af796170cc0233768` |
| Duplicate body values | `c77a067bb0f3a41346e11b136460d1c5c9b7ec88` | `6b48a3c32611e8024d11f0752751972f6cc95341` |
| Mapping identity and exact audits | `e67872cdd2f93594bf6b7d43f9ba657e79fc01a6` | `db3c00b4162541fdb2bba5f9ac446cc15f8a953c` |
| Omitted composite collections | `1b367cfaf5e291e9abebf2651a16e781f14d0ee8` | `e4e26c48a7d21bafcf57df10bb31384fb92613d7` |
| Truthful policy audit | `0aff73fcfecd0701e01e1308a2b50c8cd8104748` | `1b6e8cdfa079d87f79d0e59625aa202ccfff98e9` |
| Audit, commit and concurrent-claim faults | `b4e6575151e80bf569cb176d54edce55aa348b87` | Covered by the preceding transactional implementation |
| One composite frontend request | `e5b0ccb8ed981e349cd1bbf4d9e11a74107f7c7d` | `e89d09954f540c05a84f149f156f4f5209448e75` |
| Update lost-response recovery | `0e7fc95e7c74f94edba34491f317fa0d358eaa63` | `cd9eaa40808723d79aa5cbedd241f85a034bc6a8` |
| Create lost-response recovery | `76ab467deb27d13f4ea11a58e01a744dfd2e22ac` | `5c0bb4901f1ede950b89498b8d2b576bbcfbed73` |
| Draft/status/submission lock | `155ed8dc92894e2934b549a2579ff7cf78ff32a2` | `232b11389a8dfcff5e5ec9990f82c491dbeae631` |
| Failed reconciliation read | `a0d226c8b5dbf5a7ebb34b376ab2826a907c23f0` | `9a7357f6ab457d4bcc8c52341dc95767534fa4c8` |
| Publish authoritative recovery cache | `d91771bde0bf1f71e127b1300206999e52b9678b` | `fc0c75230618cc8d09ef3fd29d3667686b85fd60` |
| Response preparation before commit | `850511d788380e48618d13abbfc4e60cfc775349` | `3faa005025b070205c98e937f93bf2bc062a46c8` |
| Stale-cache create recovery | `ada8e0e19d16c08eb27051b82f1302d8b876e3f8` | `d22299186648c0f5db8068573a17ce6ff74021bd` |
| Frontend omitted-field preservation | `cf8dcc453c10fa6b6cfc3e96e8779f15b570ebc1` | `67b5a17b0cd2c4c13878772c4b64f0978ea8bc76` |

The warranted REFACTOR commit is `aa1c79591fc606b93b0647ef66f0234a50ea00e4`. Isolated Chromium proof is `024dc4c632f7ae452cb9900ea4dee86bf491e6dd`; `bbb7d3421a07eb04c0866acc47a87fa6c6e9f1a2` adds the build-safe typed deferred controls.

## Browser proof

Classification: isolated Playwright Chromium with disposable mocked HTTP state. Three tests passed in 12.2 seconds.

| Viewport | Locale/direction | Covered behavior |
| ---: | --- | --- |
| 1440 | EN/LTR | Create with two mappings; duplicate click/Enter suppression; update remove/add with retained mapping ID; injected 409 with unchanged authoritative state; correction/retry; cancel/reopen/reload. |
| 768 | AR/RTL | Lost committed response reconciles to success; lost uncommitted response remains uncertain with preserved draft; localized correction/retry; logical layout. |
| 375 | EN/LTR | Cancelled draft emits no write; create with two mappings remains usable without horizontal document overflow. |

Across eight logical Save attempts, Chromium observed exactly eight role writes: two POSTs and six PUTs. Every Save emitted one role write, including the injected conflict and the two aborted-response cases. It observed **zero** standalone mapping POST/DELETE requests. The two request failures were the deliberately aborted committed/uncommitted responses. No LLM, query generation, query submission or source execution route was called.

## Gates

| Gate | Result |
| --- | --- |
| Focused role/mapping/audit/permission/OpenAPI/PostgreSQL tests | 168 passed in 6.67s |
| Real PostgreSQL transaction/fault/concurrency file | 11 passed in 4.22s |
| Backend unit foundation | 2,541 passed, 44 deselected in 65.75s; three pre-existing warnings |
| Runtime/canonical/generated OpenAPI parity | 64 = 64 = 64; 21 canonical tests passed |
| Canonical and generated-client deterministic checks | Passed |
| Ruff check / format check | Passed; 453 files formatted |
| Focused frontend | 70 passed across three files |
| Full Vitest | 1,074 passed across 74 files in 12.07s |
| ESLint / typecheck / production build / CSS lint | Passed |
| Isolated Chromium | 3 passed in 12.2s |
| Authoritative GitHub CI | `backend-test` and `frontend-test` passed in run `31766725883` on `d14831e1016441d07d6736a3132e9309f78716d2` |
| `git diff --check` | Passed |
| Test Guard / Clean Code Guard / Vercel React guidance / Docs Guard | Passed |

The production build emitted only the repository's existing large-chunk warning. The backend foundation emitted the same three pre-existing unawaited-AsyncMock warnings. An initial attempt to run two database-backed pytest processes concurrently caused fixture interference; both gates passed when rerun sequentially against the shared test database.

## Cleanup and next gate

Disposable PostgreSQL roles, mappings, policies, audit rows, trigger and function were removed in test `finally` blocks. `/tmp` Playwright reports, videos and screenshots were removed. The protected baseline remains exactly 14 modified tracked PNGs, seven historical untracked screenshots and two trace archives; none was staged, regenerated, reverted or deleted.

CHUNK-17 remains blocked until this focused PR is squash-merged, its branch is deleted and local main is synchronized.
