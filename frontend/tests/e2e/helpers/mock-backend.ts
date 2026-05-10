import type { Page, Route } from '@playwright/test';
import type { QueryResult, EvaluatorRejection, RefinePrompt, AcceptedQuerySummary, HistoryListResponse, ErrorResponse } from '../../src/api/generated/types.gen';

// ─────────────────────────────────────────────────────────────────────────────
// Playwright page.route() factories for US-2 frontend E2E isolation.
// The backend state machine lives on phase1-us2-be-routers; these mocks let
// the FE branch test its own state-machine wiring without waiting for BE.
// After Wave-3 merge (Chunk 3.9) these routes can be removed for full-stack E2E.
// ─────────────────────────────────────────────────────────────────────────────

const FIRST_RESULT: QueryResult = {
  kind: 'result',
  attempt_id: 'attempt-mock-1',
  question: 'How many actors?',
  generated_sql: 'SELECT count(*) FROM actor;',
  columns: [{ name: 'count', type: 'bigint' }],
  rows: [[200]],
  row_count: 1,
  attempt_number: 1,
  is_last_auto_retry: false,
};

const REFINE_PROMPT: RefinePrompt = {
  kind: 'refine',
  message_key: 'query.refine.message',
  should_refine: true,
};

/** Intercept /query/submit and return a successful QueryResult. */
export const mockSubmitSuccess = (page: Page) =>
  page.route('**/query/submit', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(FIRST_RESULT),
    });
  });

/** Intercept /query/submit and return a 422 EvaluatorRejection. */
export const mockSubmitEvaluatorRejected = (page: Page) =>
  page.route('**/query/submit', async (route: Route) => {
    const body: EvaluatorRejection = {
      message_key: 'query.evaluator.rejected',
      violations: [
        {
          rule: 'UnsafePattern',
          message_key: 'evaluator.violation.unsafePattern',
          message_params: { pattern: 'pg_sleep' },
        },
      ],
    };
    await route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify(body) });
  });

/** Intercept /query/submit and return a 504 timeout ErrorResponse. */
export const mockSubmitTimeout = (page: Page) =>
  page.route('**/query/submit', async (route: Route) => {
    const body: ErrorResponse = {
      error: 'timeout',
      message_key: 'error.timeout',
    };
    await route.fulfill({ status: 504, contentType: 'application/json', body: JSON.stringify(body) });
  });

/** Intercept /query/submit and return a 409 concurrent ErrorResponse. */
export const mockSubmitConcurrent = (page: Page) =>
  page.route('**/query/submit', async (route: Route) => {
    const body: ErrorResponse = {
      error: 'concurrent',
      message_key: 'error.concurrent',
    };
    await route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify(body) });
  });

/** Intercept /query/submit and return a 502 LLM-unavailable ErrorResponse. */
export const mockSubmitLLMUnavailable = (page: Page) =>
  page.route('**/query/submit', async (route: Route) => {
    const body: ErrorResponse = {
      error: 'llm_unavailable',
      message_key: 'error.llmUnavailable',
    };
    await route.fulfill({ status: 502, contentType: 'application/json', body: JSON.stringify(body) });
  });

/**
 * Intercept /query/reject.
 * - 'result'  → returns a new QueryResult (auto-retry). Use `count` to control
 *               how many retries before switching to refine (callCount === count gets is_last_auto_retry=true).
 *               After `count` calls, subsequent calls return refine automatically.
 * - 'refine'  → returns RefinePrompt immediately.
 * - 'concurrent' → returns 409.
 * - 'attempt_invalid' → returns 400.
 */
export const mockReject = (
  page: Page,
  response: 'result' | 'refine' | 'concurrent' | 'attempt_invalid',
  count = 0
) => {
  let callCount = 0;
  return page.route('**/query/reject', async (route: Route) => {
    callCount++;
    if (response === 'result') {
      if (callCount <= count) {
        const isLast = callCount === count;
        const body: QueryResult = {
          kind: 'result',
          attempt_id: `attempt-mock-after-reject-${callCount}`,
          question: 'How many actors?',
          generated_sql: `SELECT count(*) FROM customer WHERE retry = ${callCount};`,
          columns: [{ name: 'count', type: 'bigint' }],
          rows: [[599 + callCount]],
          row_count: 1,
          attempt_number: 1 + callCount,
          is_last_auto_retry: isLast,
        };
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
        return;
      }
      // fall through to refine after count exhausted
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(REFINE_PROMPT) });
      return;
    }
    if (response === 'refine') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(REFINE_PROMPT) });
      return;
    }
    if (response === 'concurrent') {
      const body: ErrorResponse = { error: 'concurrent', message_key: 'error.concurrent' };
      await route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify(body) });
      return;
    }
    const body: ErrorResponse = { error: 'attempt_invalid', message_key: 'error.attemptInvalid' };
    await route.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify(body) });
  });
};

/** Intercept /query/accept and return 201 AcceptedQuerySummary. */
export const mockAccept = (page: Page, summary?: AcceptedQuerySummary) =>
  page.route('**/query/accept', async (route: Route) => {
    const body: AcceptedQuerySummary = summary ?? {
      id: 'f9e8d7c6-b5a4-4c3b-2a1d-0e9f8d7c6b5a',
      question_text: 'How many actors?',
      generated_sql: 'SELECT count(*) FROM actor;',
      accepted_at: new Date().toISOString(),
    };
    await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(body) });
  });

/** Intercept GET /history and return a canned list. */
export const mockHistoryList = (page: Page, history?: HistoryListResponse) =>
  page.route('**/history', async (route: Route) => {
    const body: HistoryListResponse = history ?? {
      items: [
        {
          id: 'f9e8d7c6-b5a4-4c3b-2a1d-0e9f8d7c6b5a',
          question_text: 'How many actors?',
          generated_sql: 'SELECT count(*) FROM actor;',
          accepted_at: new Date().toISOString(),
        },
      ],
      total: 1,
      next_cursor: null,
    };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });

/** Intercept /query/submit with a custom result (useful for refined questions). */
export const mockSubmitCustom = (page: Page, result: QueryResult) =>
  page.route('**/query/submit', async (route: Route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(result) });
  });

/**
 * Intercept /query/submit and return a 422 EvaluatorRejection with specific violations.
 * Each violation should have `rule` (machine-readable identifier) and optional `message_params`.
 */
export const mockSubmitEvaluatorRejectedWithViolations = (
  page: Page,
  violations: Array<{
    rule: string;
    message_key: string;
    message_params?: Record<string, unknown>;
  }>
) =>
  page.route('**/query/submit', async (route: Route) => {
    const body: EvaluatorRejection = {
      message_key: 'query.evaluator.rejected',
      violations: violations.map((v) => ({
        rule: v.rule,
        message_key: v.message_key,
        message_params: v.message_params ?? null,
      })),
    };
    await route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify(body) });
  });

/**
 * Intercept GET /history and return an empty list (useful for asserting no rows were written).
 */
export const mockHistoryEmpty = (page: Page) =>
  page.route('**/history', async (route: Route) => {
    const body: HistoryListResponse = {
      items: [],
      total: 0,
      next_cursor: null,
    };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });

/** Intercept GET /history/{id} and return a single detail item. */
export const mockHistoryDetail = (page: Page, detail: Record<string, unknown>) =>
  page.route('**/history/*', async (route: Route) => {
    const url = new URL(route.request().url());
    if (url.pathname.match(/\/history\/[^/]+$/)) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(detail) });
      return;
    }
    await route.fallback();
  });
