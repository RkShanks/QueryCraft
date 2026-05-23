# Frontend Foundation Gates Evidence (Wave 16.0 - Baseline)

This document contains the verbatim output of the frontend foundation quality gates executed on the `main` baseline branch prior to any Phase 4 code modifications.

## 1. Vitest Test Suite (`npm run test -- --run`)

**Command:**
```bash
npm run test -- --run
```

**Status:** FAILED (Exit Code 1)

**Verbatim Output:**
```
> frontend@0.0.0 test
> vitest --passWithNoTests --run


 RUN  v4.1.5 /home/avril/QueryCraft/frontend

  ❯ tests/lint/no-physical-tailwind.test.ts (2 tests | 1 failed) 15ms
      ✓ skips if dist/ does not exist 1ms
      × zero physical-direction utilities in built CSS 9ms

  ❯ src/pages/AskQuestionPage.test.tsx (15 tests | 1 failed) 2438ms
      ✓ should allow asking a question and displaying results 297ms
      ✓ should handle evaluator rejection 54ms
      ✓ should handle successful acceptance 118ms
      ✓ shows no database available alert when submitting without connectionId (T-461 regression) 44ms
      ✓ shows ResultTable on successful submit 38ms
      ✓ shows EvaluatorRejectionBanner and hides ResultTable on evaluator rejected 54ms
      ✓ shows TimeoutBanner on timeout submit 52ms
      × shows concurrent error toast on 409 1043ms
      ✓ shows LLM unavailable toast on 502 83ms
      ✓ clicking Reject returns new ResultTable on success 116ms
      ✓ clicking Regenerate returns new ResultTable on success 86ms
      ✓ double-reject shows RefinePromptBanner 125ms
      ✓ new submit clears all banners 112ms
      ✓ Try Refining CTA resets input and clears banners 124ms
      ✓ Try Again CTA in TimeoutBanner re-submits 87ms

 ⎯⎯⎯⎯⎯⎯⎯ Failed Tests 2 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  tests/lint/no-physical-tailwind.test.ts > T-181: built CSS bundle has no physical-direction utilities > zero physical-direction utilities in built CSS
AssertionError: expected [ { …(3) } ] to deeply equal []

- Expected
+ Received

- []
+ [
+   {
+     "file": "assets/index-DrVCn5Eu.css",
+     "line": 2,
+     "text": "... .right-4{right:calc(var(--spacing) * 4)} ..."
+   },
+ ]

  ❯ tests/lint/no-physical-tailwind.test.ts:59:24
      57|       }
      58|     }
      59|     expect(violations).toEqual([]);
        |                         ^
      60|   });
      61| });

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/2]⎯

 FAIL  src/pages/AskQuestionPage.test.tsx > AskQuestionPage US-2 State Machine > shows concurrent error toast on 409
TestingLibraryElementError: Unable to find an element with the text: /already being processed/i. This could be because the text is broken up by multiple elements. In this case, you can provide a function for your text matcher to make your matcher more flexible.

  ❯ Proxy.waitForWrapper node_modules/@testing-library/dom/dist/wait-for.js:163:27
  ❯ src/pages/AskQuestionPage.test.tsx:181:11
      179|     fireEvent.click(screen.getByRole('button', { name: /ask/i }));
      180|
      181|     await waitFor(() => {
         |           ^
      182|       expect(screen.getByText(/already being processed/i)).toBeInTheDo…
      183|     });

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[2/2]⎯

 Test Files  2 failed | 49 passed (51)
      Tests  2 failed | 432 passed (434)
   Start at  04:20:29
   Duration  7.82s (transform 5.17s, setup 17.64s, import 12.95s, tests 18.36s, environment 49.50s)
```

---

## 2. ESLint Static Analysis (`npm run lint`)

**Command:**
```bash
npm run lint
```

**Status:** PASSED (Exit Code 0)

**Verbatim Output:**
```
> frontend@0.0.0 lint
> eslint .
```

---

## 3. TypeScript Compilation Checks (`npm run typecheck`)

**Command:**
```bash
npm run typecheck
```

**Status:** PASSED (Exit Code 0)

**Verbatim Output:**
```
> frontend@0.0.0 typecheck
> tsc --noEmit
```

> [!NOTE]
> While `npm run typecheck` passes, it is because it runs `tsc --noEmit` on the root workspace config which utilizes project references without passing the `--build` or `--project` flags. This means TS referenced configurations like `tsconfig.app.json` and `tsconfig.node.json` are not actively checked in the raw `typecheck` script, but are checked during `npm run build` (via `tsc -b`).

---

## 4. Production Build (`npm run build`)

**Command:**
```bash
npm run build
```

**Status:** FAILED (Exit Code 2)

**Verbatim Output:**
```
> frontend@0.0.0 build
> tsc -b && vite build

tests/e2e/history-list-detail.spec.ts:62:113 - error TS2353: Object literal may only specify known properties, and 'schema' does not exist in type 'AcceptedQuerySummary'.

62         { id: '1', question_text: 'Accepted Q', generated_sql: 'SELECT 1', accepted_at: '2026-05-11T00:00:00Z', schema: 'public' },
                                                                                                                   ~~~~~~

tests/e2e/i18n-audit.spec.ts:2:44 - error TS2880: Import assertions have been replaced by import attributes. Use 'with' instead of 'assert'.

2 import en from '../../src/locales/en.json' assert { type: 'json' };
                                             ~~~~~~


Found 2 errors.
```

---

## 5. CSS Style Linting (`npm run lint:css`)

**Command:**
```bash
npm run lint:css
```

**Status:** PASSED (Exit Code 0)

**Verbatim Output:**
```
> frontend@0.0.0 lint:css
> stylelint "src/**/*.{css,scss}"
```
