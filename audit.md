# US-1 Frontend Audit

## Baseline Gates (after restoring uncommitted deps)
- `npm run lint`: 1 warning (TanStack Table incompatible-library), 0 errors
- `npm run lint:css`: clean
- `npm run typecheck`: clean
- `npm test -- --run`: 6 files, 24 passed
- `npm run build`: success

## 1.1 — T-ID Accounting (US-1 Frontend: T-061..T-073)

| T-ID | Status | Notes |
|------|--------|-------|
| T-061 | DONE | `frontend/src/api/generated/*` exists, types match backend |
| T-062 | DONE | `frontend/src/hooks/useAuth.test.tsx` exists and passes |
| T-063 | DONE | `frontend/src/hooks/useAuth.ts` exports useSignIn/useCurrentUser/useSignOut |
| T-064 | DONE | `frontend/src/hooks/useQuerySubmit.test.tsx` exists and passes |
| T-065 | NEEDS REWORK | `useQuerySubmit.ts` exports useRejectQuery + useRegenerateQuery (US-2 creep). Hook also exports useAcceptQuery and useHistory in same file instead of separate files as implied by tasks. Also returns plain mutation data, NOT a discriminated union with refine_prompt (good). But needs cleanup. |
| T-066 | DONE | `frontend/src/components/auth/SignInForm.test.tsx` exists and passes |
| T-067 | DONE | `SignInForm.tsx` + `SignInPage.tsx` exist |
| T-068 | DONE | `frontend/src/components/query/QueryInput.test.tsx` exists and passes |
| T-069 | DONE | `QueryInput.tsx` exists |
| T-070 | NEEDS REWORK | `ResultTable.test.tsx` exists but tests Reject/Regenerate buttons (US-2). Needs cleanup. |
| T-071 | NEEDS REWORK | `ResultTable.tsx` + `SqlDisplay.tsx` + `QueryActions.tsx` exist, but QueryActions has Reject+Regenerate buttons (US-2). ResultTable passes onReject/onRegenerate props. |
| T-072 | NEEDS REWORK | `AskQuestionPage.test.tsx` exists but tests reject/regenerate paths and refine_prompt UI (US-2). Needs cleanup. |
| T-073 | NEEDS REWORK | `AskQuestionPage.tsx` has reject/regenerate handlers, refinePrompt state, and Toast UI. |

## 1.2 — Scope Creep Audit (US-2 Leakage)

### Reject
- `frontend/src/hooks/useQuerySubmit.ts:27-31` — `useRejectQuery` hook (MUST REMOVE)
- `frontend/src/components/query/ResultTable.tsx:16` — `onReject` prop (MUST REMOVE)
- `frontend/src/components/query/ResultTable.tsx:84` — passes `onReject` to QueryActions (MUST REMOVE)
- `frontend/src/components/query/QueryActions.tsx:7,15,24-27` — Reject button + handler prop (MUST REMOVE)
- `frontend/src/pages/AskQuestionPage.tsx:8,39,84-101,162` — `useRejectQuery`, `handleReject`, passes `onReject` (MUST REMOVE)
- `frontend/src/pages/AskQuestionPage.test.tsx` — tests reject flow (MUST REMOVE / UPDATE)

### Regenerate
- `frontend/src/hooks/useQuerySubmit.ts:33-36` — `useRegenerateQuery` hook (MUST REMOVE)
- `frontend/src/components/query/ResultTable.tsx:17` — `onRegenerate` prop (MUST REMOVE)
- `frontend/src/components/query/ResultTable.tsx:85` — passes `onRegenerate` to QueryActions (MUST REMOVE)
- `frontend/src/components/query/QueryActions.tsx:8,16,29-34` — Regenerate button + handler prop (MUST REMOVE)
- `frontend/src/pages/AskQuestionPage.tsx:9,40,103-116,163` — `useRegenerateQuery`, `handleRegenerate`, passes `onRegenerate` (MUST REMOVE)
- `frontend/src/pages/AskQuestionPage.test.tsx` — tests regenerate flow (MUST REMOVE / UPDATE)

### refine_prompt
- `frontend/src/pages/AskQuestionPage.tsx:26` — `refinePrompt` state (MUST REMOVE)
- `frontend/src/pages/AskQuestionPage.tsx:44` — `setRefinePrompt(null)` (MUST REMOVE)
- `frontend/src/pages/AskQuestionPage.tsx:95,110` — `setRefinePrompt(data)` in reject/regenerate handlers (MUST REMOVE)
- `frontend/src/pages/AskQuestionPage.tsx:169-183` — refinePrompt UI section (MUST REMOVE)
- `frontend/src/pages/AskQuestionPage.tsx:11` — `RefinePrompt` type import (MUST REMOVE)

Note: `rejectQuery` and `regenerateQuery` imports from generated SDK are type-safe imports from the API client. The functions themselves are US-2 backend endpoints. Removing the imports is fine.

## 1.3 — Missing Component Audit

| Component | File Exists | Test Exists | Notes |
|-----------|------------|-------------|-------|
| SignInForm.tsx | YES | YES | `frontend/src/components/auth/SignInForm.tsx` |
| SignInPage.tsx | YES | NO | No dedicated test file; SignInForm has tests |
| AskQuestionPage.tsx | YES | YES | But tests cover US-2 paths |
| QuestionInput.tsx | NO | NO | Named QueryInput.tsx instead — acceptable |
| SubmitButton.tsx | NO | NO | Part of QueryInput — acceptable |
| ResultTable.tsx | YES | YES | But tests cover US-2 paths |
| SqlDisplay.tsx | YES | NO | No dedicated test; tested via ResultTable/AskQuestionPage |
| AcceptButton.tsx | NO | NO | Rolled into QueryActions.tsx with Reject/Regenerate — needs extraction or rename |
| HistoryList.tsx | NO | NO | MISSING |
| HistoryPage.tsx | YES | NO | Stub page only |

## 1.4 — Missing Hook Audit

| Hook | File Exists | Test Exists | Notes |
|------|------------|-------------|-------|
| useSignIn | YES (in useAuth.ts) | YES (in useAuth.test.tsx) | T-063 Done |
| useCurrentUser | YES (in useAuth.ts) | YES (in useAuth.test.tsx) | T-063 Done |
| useSignOut | YES (in useAuth.ts) | YES (in useAuth.test.tsx) | T-063 Done |
| useSubmitQuestion | YES (in useQuerySubmit.ts) | YES (in useQuerySubmit.test.tsx) | T-065 Done (but with US-2 exports) |
| useAcceptQuery | YES (in useQuerySubmit.ts) | YES (in useQuerySubmit.test.tsx) | MISSING as separate file per audit list, but exists as export. Tests cover it. |
| useHistory | YES (in useQuerySubmit.ts) | YES (in useQuerySubmit.test.tsx) | MISSING as separate file per audit list, but exists as export. Tests cover it. |

Decision: The hooks exist as exports from consolidated files. This is acceptable per T-062/T-063/T-064/T-065 descriptions which name the files. The test coverage is adequate. However, `useAcceptQuery` and `useHistory` should be formally recognized as done.

## 1.5 — MSW Handler Audit

All 6 required handlers present in `frontend/src/test/handlers.ts`:
- POST /auth/sign-in: YES (returns 200 + user)
- GET /auth/me: YES (returns 200 + user)
- POST /auth/sign-out: YES (returns 204)
- POST /query/submit: YES (returns QueryResult, NO refine_prompt branch — correct!)
- POST /query/accept: YES (returns 201 + summary)
- GET /history: YES (returns 200 + paginated items)

NO /query/reject or /query/regenerate handlers present. Good.

However, handlers lack overridable error branches. The tests override via `server.use()` inline, which is the standard MSW pattern. This is acceptable.

## 1.6 — Router Wiring Audit

`frontend/src/App.tsx`:
- Routes `/login` → LoginPage (should be `/sign-in` per plan v3)
- Routes `/query` → QueryPage (should be `/` per plan v3, or `/ask`)
- Routes `/history` → HistoryPage (correct)
- No auth guards on protected routes
- No redirect from `/` based on auth state

`frontend/src/main.tsx`:
- No QueryClientProvider wrapper (moved to App.tsx via QueryProvider)
- Missing global error handler for 401 redirect

## 1.7 — i18n Key Audit

Missing or wrong keys in `frontend/src/locales/en.json`:

### auth.signIn.*
- `auth.signIn.title` — present ✓
- `auth.signIn.username.label` — MISSING (has `auth.signIn.username` without `.label`)
- `auth.signIn.password.label` — MISSING (has `auth.signIn.password` without `.label`)
- `auth.signIn.submit` — present ✓
- `auth.signIn.signingIn` — MISSING (SignInForm uses `auth.signIn.loading`)
- `auth.signIn.error.invalidCredentials` — MISSING (has `auth.signIn.error`)
- `auth.signIn.error.network` — MISSING

### auth.signOut.label
- MISSING (has `nav.signOut` instead)

### query.input.*
- `query.input.placeholder` — MISSING (has `query.ask.placeholder`)
- `query.input.submit` — MISSING (has `query.ask.submit`)
- `query.input.submitting` — MISSING (has `query.ask.maxLength` which is wrong key)

### query.result.*
- `query.result.title` — MISSING (has `query.result.title` with value "Generated SQL" — wrong semantics)
- `query.result.sqlHeading` — MISSING (has `query.result.sql_label` in code)
- `query.result.tableHeading` — MISSING
- `query.result.empty` — MISSING (has `query.result.noData`)

### query.actions.*
- `query.actions.accept` — MISSING (code uses `query.action.accept` singular)
- `query.actions.accepting` — MISSING (code uses `query.action.accepting`)
- `query.actions.accepted` — MISSING
- NO reject/regenerate keys in en.json (good!)

### history.*
- `history.title` — present ✓
- `history.empty` — present ✓
- `history.column.question` — MISSING (has `history.question`)
- `history.column.sql` — MISSING (has `history.sql`)
- `history.column.acceptedAt` — MISSING (has `history.date`)
- `history.loadMore` — MISSING
- `history.loadingMore` — MISSING

### error.*
- `error.unauthorized` — present ✓
- `error.network` — MISSING
- `error.unknown` — present ✓
- `error.validation.questionEmpty` — present ✓
- `error.validation.questionTooLong` — MISSING
- `error.validation.unknown` — MISSING

### query.refinePrompt.*
- `query.refine.title` — PRESENT in code (AskQuestionPage.tsx:175) but NOT in en.json. Code uses defaultValue fallback.
- No other refinePrompt keys in en.json.

## 1.8 — Dependency Drift Audit

New dependencies added by Gemini (uncommitted):
- `@radix-ui/react-toast` — US-2 Toast component. Non-essential to US-1. Plan says "Radix UI primitives" but US-1 only needs minimal inline alerts. **REMOVE**.
- `@tanstack/react-table` — Required for ResultTable. **KEEP**.
- `clsx` + `tailwind-merge` — Utility libs used by Toast.tsx and cn() pattern. Only needed if Toast stays. **REMOVE with Toast**.
- `lucide-react` — Used by AskQuestionPage for icons (History, Database, AlertCircle, CheckCircle2). Plan v3 does not list it. **REMOVE or justify**: icons are nice-to-have but not essential for US-1. However, removing them requires replacing with inline SVGs or text, which is non-trivial. **KEEP with justification**: used for nav icons in AskQuestionPage, removal cascades into component rewrites.
- `react` upgraded from `^18.x` to `^19.2.5` in package.json. The committed code uses React 19. **This is a major drift from plan v3 which specifies React 18**. However, reverting to React 18 would cause peer dep issues with other packages. **KEEP with justification**: React 19 is backward-compatible for our usage, and all tests pass.

## Summary of Required Work

### Phase 2 — Cleanup
1. Remove Reject/Regenerate from QueryActions, ResultTable, AskQuestionPage, useQuerySubmit
2. Remove refine_prompt state machine from AskQuestionPage
3. Remove/replace Radix Toast with minimal inline alert (removes @radix-ui/react-toast, clsx, tailwind-merge deps)
4. Fix i18n keys in en.json to match plan v3
5. Fix router wiring: `/sign-in` instead of `/login`, auth guards, root redirect
6. Update tests to remove US-2 assertions

### Phase 3 — Completion
1. Rename QueryActions → AcceptButton (or create AcceptButton)
2. Build HistoryList component + test
3. Build HistoryPage integration with HistoryList + test
4. Add missing i18n keys
5. Add router auth guards + 401 global error handler
6. Wire `/` → AskQuestionPage (auth-guarded) and `/sign-in` → SignInPage
