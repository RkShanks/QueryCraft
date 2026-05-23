# Phase 4 Baseline Audit Report (Wave 16.0)

This report consolidates the baseline audit findings executed as part of Phase 4 Wave 16.0 on the `main` branch codebase prior to the Arabic UI translation and RTL layout polish.

## 1. Executive Summary

The Wave 16.0 Baseline Audit was executed to establish a stable baseline state and confirm that all frontend foundation gates, i18n key mappings, and CSS direction standards are documented. The findings confirm that while static linters and i18n key synchronization are excellent, there are specific test and build regressions on `main` that must be addressed during Wave 16.1/16.2.

No product code was modified during this wave, adhering strictly to the baseline audit constraints.

---

## 2. Component Audits Summary

### 2.1 Frontend Foundation Gates (T-500)
- **Quality Gates Status:** **FAILED**
- **Detailed Log:** [frontend-gates.md](file:///home/avril/QueryCraft/specs/004-arabic-rtl-verification-polish/evidence/wave-16.0/frontend-gates.md)
- **Status of Gates:**
  - `npm run test -- --run` (Vitest): **FAILED** (2/434 tests failed: physical Tailwind bundle violation and concurrent error toast regression)
  - `npm run lint` (ESLint): **PASSED**
  - `npm run typecheck` (TypeScript): **PASSED** (Workspace-level compilation check without project builds)
  - `npm run build` (Vite/TS Build): **FAILED** (2 TypeScript build compilation errors in E2E test files)
  - `npm run lint:css` (Stylelint): **PASSED**

### 2.2 i18n Key Parity Audit (T-501)
- **Parity Status:** **100% Match (Bi-directional Complete)**
- **Detailed Log:** [i18n-parity.md](file:///home/avril/QueryCraft/specs/004-arabic-rtl-verification-polish/evidence/wave-16.0/i18n-parity.md)
- **Key Metrics:**
  - Total English Keys (`en.json`): **262**
  - Total Arabic Keys (`ar.json`): **262**
  - Missing keys (EN -> AR): **0**
  - Missing keys (AR -> EN): **0**
  - Empty translations: **0**

### 2.3 Physical CSS Direction Audit (T-502)
- **Compliance Status:** **1 Violation Found**
- **Detailed Log:** [css-direction-audit.md](file:///home/avril/QueryCraft/specs/004-arabic-rtl-verification-polish/evidence/wave-16.0/css-direction-audit.md)
- **Key Metrics:**
  - Raw CSS Property Violations: **0**
  - Physical Tailwind Class Violations: **1**
  - Violation details: `right-4` used on line 480 of [WorkspacePage.tsx](file:///home/avril/QueryCraft/frontend/src/pages/WorkspacePage.tsx#L480).

---

## 3. Detailed Baseline Findings (Wave 16.1/16.2 Action Items)

Four baseline issues have been identified on `main` that must be remediated in the next wave (Wave 16.1):

### Finding F-001: Physical Tailwind Class Violation in Workspace Sidebar
- **Impact:** Fails quality gate `no-physical-tailwind.test.ts` on built CSS.
- **Location:** [WorkspacePage.tsx:480](file:///home/avril/QueryCraft/frontend/src/pages/WorkspacePage.tsx#L480)
- **Remediation:** Replace the physical positioning utility `right-4` with the logical equivalent `end-4`.

### Finding F-002: Vitest State Machine Regression in AskQuestionPage
- **Impact:** Fails unit test suite.
- **Failure Message:** `TestingLibraryElementError: Unable to find an element with the text: /already being processed/i.`
- **Location:** [AskQuestionPage.test.tsx:181](file:///home/avril/QueryCraft/frontend/src/pages/AskQuestionPage.test.tsx#L181)
- **Remediation:** Investigate asynchronous state updates and modal rendering logic in the test suite to ensure toast alerts are properly rendered and timed in mock environments.

### Finding F-003: TypeScript Build Error in E2E History Test
- **Impact:** Fails production build gate (`npm run build`).
- **Failure Message:** `error TS2353: Object literal may only specify known properties, and 'schema' does not exist in type 'AcceptedQuerySummary'.`
- **Location:** [history-list-detail.spec.ts:62](file:///home/avril/QueryCraft/frontend/tests/e2e/history-list-detail.spec.ts#L62)
- **Remediation:** Update the E2E test data definition or align the mock payload schema key to fit the expected `AcceptedQuerySummary` type definition.

### Finding F-004: Deprecated Import Assertion syntax in E2E i18n Test
- **Impact:** Fails production build gate (`npm run build`).
- **Failure Message:** `error TS2880: Import assertions have been replaced by import attributes. Use 'with' instead of 'assert'.`
- **Location:** [i18n-audit.spec.ts:2](file:///home/avril/QueryCraft/frontend/tests/e2e/i18n-audit.spec.ts#L2)
- **Remediation:** Modernize the import attributes assertion syntax from `assert { type: 'json' }` to the standard ES2025 compliant syntax `with { type: 'json' }`.
