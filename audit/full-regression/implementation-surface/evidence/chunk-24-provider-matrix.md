# CHUNK-24 — non-Gemini provider evidence (IS-GAP-015)

Branch: `phase-6/wave-19.24-provider-matrix` (follow-up: `phase-6/wave-19.24-provider-null-body-followup`)
Starting synchronized main: `1bfc245448e2ff4dd7b2111065ee7ce04bdff7e9`
Tested product commits: RED `542bd34`, GREEN `81fc501`, lint wrap `c729511` (branch head at evidence time); follow-up RED `7f1d220`, GREEN `8406f13`
Date: 2026-08-25
Role: Backend Implementer / evidence runner

## Scope

Provider-agnostic behavior verification for Anthropic, OpenAI, and Ollama via a
deterministic matrix. Gemini configuration and behavior untouched. No live
provider invocation was authorized in this environment; every provider's live
smoke is classified **Setup-dependent** below. No mocks were substituted for
live-provider closure.

## Deterministic provider matrix results

All categories executed against committed code with respx HTTP-boundary mocks,
real factory/settings objects, and a hermetic fixture that removes ambient
credential variables for the duration of each test.

| # | Category | New tests | Result |
| --- | --- | ---: | --- |
| 1 | Provider selection and normalization (case normalization; empty/None → default) | 4 | Pass |
| 2 | Factory routing (anthropic/openai/gemini/ollama/stub types) | 2 | Pass |
| 3 | Missing or malformed configuration (missing keys ×3, blank settings key vs env fallback, absent-attribute env fallback) | 5 | Pass |
| 4 | Unsupported provider names fail closed | 4 | Pass |
| 5 | Invalid base URLs / models (unreachable-host characterization, default model selection, host slash normalization) | 3 | Pass |
| 6 | Provider cancellation propagation ×3 (pre-existing typed-timeout coverage re-verified green) | 3 | Pass |
| 7 | Provider HTTP/API failure: typed 401 mapping ×3 (pre-existing 429/502 coverage re-verified green) | 3 | Pass |
| 8 | Sanitized error mapping (non-JSON body ×3, missing SQL field ×3, null SQL field ×2, empty content list ×1 → constant sanitized message; no provider body text in exception messages) | 9 | Pass |
| 9 | No unintended provider fallback (fail-closed on missing key / unknown provider) | 2 | Pass |
| 10 | No secret retention (long-key cache fingerprint hides body; configuration-error message hygiene; cache isolation across keys/models) | 3 | Pass |
| 11 | Query composition compatibility (shared prompt structure across all three adapters: dialect instruction, conversation history, negative examples, minimal-form absence) | 6 | Pass |

Matrix total: **44 new deterministic cases**, all passing. Pre-existing adapter
boundary suites (success/timeout/429/502 per provider), prompt-builder suite,
lifecycle/factory suites, and Gemini dialect suites were re-run and remain green
inside them.

## Confirmed defect found and fixed within this gap

Reproduction (RED commit `542bd34`, 12 failing cases): on a structured or
unstructured 200 response without a usable SQL field, or on any 4xx response,
the Anthropic/OpenAI/Ollama adapters leaked raw framework exceptions
(`JSONDecodeError` / `KeyError` / silent `None` return / raw `HTTPStatusError`)
across their boundary instead of the required typed sanitized provider failure
recorded for these surfaces. The service layer still sanitized the outcome, so
no user-facing disclosure existed, but the adapters violated their own error
contract and P2-FR-047's malformed-response requirement.

Fix (GREEN commit `81fc501`): each of the three adapters now maps malformed
response bodies and 4xx responses to the typed unavailable error with a
constant sanitized message, mirroring the established GeminiAdapter pattern.
Signatures unchanged; no fallback behavior added; no provider body text is
embedded in any message.

Characterization kept: connection-level failures are not typed at the adapter
boundary (all four providers, including unchanged Gemini); they are sanitized by
the service layer's generic provider-failure mapping. Changing that would have
required touching Gemini, which this chunk forbids.

## Post-merge follow-up: malformed JSON container shapes

Reproduction against merged main (read-only probe, RED commit `7f1d220`,
15 failing cases): valid-JSON responses whose container shapes are malformed —
top-level null, top-level array, top-level scalar string, expected container set
to null or a scalar, and non-dict list elements — raised an untyped
interpreter-level subscript error across the Anthropic/OpenAI/Ollama boundaries
because that error class was absent from the specific exception tuple.

Fix (GREEN commit `8406f13`): `TypeError` joins the existing narrow
`(KeyError, IndexError, TypeError, ValueError)` mapping in all three adapters,
so every malformed response structure now produces `LLMUnavailable` with the
correct provider classification and the constant sanitized message. No provider
response body or raw framework exception text reaches any message; signatures,
Gemini behavior, provider-fallback absence, cancellation propagation, timeout
behavior and valid-response extraction are unchanged (no broad catch-all).

New regression coverage: 18 data-driven cases across the three adapter suites —
top-level null/array/scalar per adapter, null/scalar containers per adapter,
non-dict list elements, plus non-string leaf containers; existing missing-field
and null-leaf cases remain covered. Post-fix totals: 62 new deterministic cases
overall for this gap (44 original + 18 follow-up), focused suites 161 passed,
full backend unit foundation 2258 passed/365 skipped/44 deselected,
Ruff check/format clean, `git diff --check` clean.

IS-GAP-015 remains **Partial**: this follow-up changes deterministic coverage
only; all three live-provider smokes stay Setup-dependent with zero invocations.

## Live-provider availability (no invocation run)

| Provider | Credential present | Runtime reachable | Bounded smoke | Classification |
| --- | --- | --- | --- | --- |
| Anthropic | No | n/a | Not run | Setup-dependent |
| OpenAI | Yes | Yes | Not run — cost/invocation approval declined by owner | Setup-dependent |
| Ollama | n/a | No (runtime not installed; nothing listening locally) | Not run | Setup-dependent |

Zero external spend, zero invocations, zero retries. Credential presence was
inspected as booleans only. When an approved environment exists, exactly one
benign bounded generate call per provider closes this remainder; no code change
is required for it.

## Gates (verbatim counts)

- Focused provider + query-composition + regression subset (`tests/unit/llm`,
  retry-quota, exceptions): **161 passed** (143 original + 18 follow-up cases)
- Full backend unit foundation (`pytest tests/unit -q -m "not integration"`):
  **2258 passed, 365 skipped, 44 deselected**
- `ruff check src tests`: All checks passed
- `ruff format --check src tests`: 456 files already formatted
- `git diff --check`: clean
- Frontend gates: not required (no frontend files changed)
- Generated API parity: not required (no API/contracts changes)

## Guard reviews

- Test Guard: reviewed; HTTP boundary mocked only via respx; ambient credential
  variables removed hermetically; defect-reproduction tests retained.
- Clean Code Guard: reviewed; specific exception types re-typed with cause
  chaining, no swallowing, style mirrors existing adapter pattern.
- Docs Guard: applied to this evidence and ledger updates (status/count-only).

## Isolation and cleanup

- Normal development configuration untouched (`LLM_PROVIDER=gemini` preserved).
- No containers, databases, Redis state, temp files, logs, or browser output
  were created by this chunk; nothing to remove.
- Protected dirty baseline (pre-existing PNG/traces modifications) preserved;
  staged paths were exactly the seven implementation/test/evidence/ledger files.
- Evidence contains statuses, categories, counts, and sanitized booleans only.

## Status accounting for IS-GAP-015

- Deterministic matrix: **Pass** (gap's automated-test requirement fully met).
- One bounded live smoke per provider: **Setup-dependent** ×3 — not run, not
  faked.
- Gap overall: **Partial** — deterministic closure complete and merged;
  live-provider proof remains open strictly pending environment/approval.
