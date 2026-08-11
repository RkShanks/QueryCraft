# CHUNK-11 / IS-GAP-012 — atomic concurrent-session eviction

Status: implementation proof passed on branch `phase-6/wave-19.11-session-limit-atomic`; authoritative GitHub backend/frontend CI is pending.

Tested product commit: `00b5ad8f266d7f6156a5c3ce6ed11b59c54f5652`.

## Atomic design

- Session creation, user-index insertion, stale-member pruning, deterministic score assignment, overflow victim selection, victim session-key deletion, index TTL, and sequence TTL now happen in one Redis Lua operation.
- Tie-breaking uses a per-user Redis sequence increment inside the script. Equal timestamps are ordered by Redis linearization, not session-id text.
- New scores are clamped after the current max score, so rollout-era timestamp-scored indexes do not outrank a newly linearized login.
- Refresh uses an atomic script that only refreshes an existing key, repairs live legacy missing-index state, extends index/sequence TTLs, and returns no session for evicted or idle-expired keys.
- Refresh replacement is generation-safe: exact raw-session matches replace the payload; CAS mismatches merge only role/permission fields and keep unrelated newer session fields.
- Sign-out, idle expiry, deleted-user cleanup, local audit rollback, OIDC audit rollback, and SAML audit rollback use the shared atomic lifecycle.

## TDD commits

| Stage | Commit |
| --- | --- |
| RED race reproduction | `e87a49509ee6e3beb6199182c4a4a0eac4bff9f6` |
| RED refresh/eviction seam | `e3fe105de66ec2fcfbf74206c1e1adc559f7be5c` |
| GREEN atomic implementation | `a857495f9a4c2cd39e2305155a9baed182085c22` |
| REFACTOR key construction | `7d698fd9d5a3b9fd30412f3c9f226e15dec4eca7` |
| Focused test alignment | `8e4028ba0c7f64487cd40bd0eaae971632f6902b` |
| Transient-overlimit assertion | `bb42cc7e3a28c0d69c321f1ae7e9470f432b3e6a` |
| Cleanup edge hardening | `2e8099700abd5cc4f19da1d52c391b089fcf48d8` |
| Result privacy cleanup | `b91b50e4a770691a6a914b2d1301a94caa8ca825` |
| Ordered/isolation burst assertions | `00b5ad8f266d7f6156a5c3ce6ed11b59c54f5652` |

## Live Redis proof

Disposable Redis proof used one isolated test DB, flushed before and after proof.

| Scenario | Attempts | Limit | Live indexed | Usable live | Evicted 401 | Extra invariant |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Direct atomic equal-time writes | 8 | 3 | 3 | N/A | N/A | no operation reported over limit |
| Concurrent AuthService local-login burst | 8 | 3 | 3 | 3 | 5 | index key = 1; sequence key = 1 |
| Concurrent SsoService OIDC burst | 8 | 3 | 3 | 3 | 5 | index key = 1; sequence key = 1 |

Cleanup proof: final disposable Redis DB size was zero after cleanup.

## Focused gates

| Gate | Result |
| --- | --- |
| Real Redis concurrent session matrix, AuthService local paths, SSO paths, stale index, rollout, TTL, cleanup, audit rollback, API outage | `35 passed, 6 skipped` |
| Auth/session refresh and admin permission-refresh regressions | included above and separately `10 passed, 5 skipped` before final batch |
| OIDC/SAML callback and replay regressions, middleware Redis lifecycle, API auth outage, CHUNK-07 identity/permission regressions | `75 passed, 15 skipped` |
| Backend unit foundation (`tests/unit -m "not integration"`) | `2102 passed, 365 skipped, 44 deselected, 3 warnings` |
| Ruff check | `src tests` passed |
| Ruff format check | `src tests` already formatted |
| JSON validation | Evidence JSON and matrix JSON passed |
| `git diff --check` | passed |

All evidence records only counts, booleans, limits, statuses, and commit IDs. No session IDs, cookies, OIDC/SAML tokens, assertions, or complete session payloads were retained.

## Cleanup and protected baseline

- Disposable live-proof Redis keys were removed; DB size ended at zero.
- Disposable container count after cleanup: 0; disposable network count after cleanup: 0.
- The protected PNG/screenshot/trace baseline remained unstaged and untouched.
- CHUNK-12 remains gated on authoritative backend/frontend CI and merge completion; no CHUNK-12 work was started.
