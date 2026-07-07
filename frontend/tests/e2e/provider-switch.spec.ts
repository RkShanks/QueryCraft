import { test, expect, type Page, type Route } from '@playwright/test';
import type { QueryResult, AcceptedQuerySummary, AcceptedQueryDetail, HistoryListResponse } from '../../src/api/generated/types.gen';

import { mockConnections, mockLocalAuth } from './helpers/mock-backend';
import { signInLocalUser } from './helpers/auth';

async function signIn(page: Page) {
  await mockLocalAuth(page);
  await mockConnections(page);
  await signInLocalUser(page);
  await expect(page.locator('textarea')).toBeEnabled({ timeout: 5_000 });
}

const OLLAMA_RESULT: QueryResult = {
  kind: 'result',
  attempt_id: 'attempt-ollama-1',
  question: 'How many actors?',
  generated_sql: 'SELECT count(*) FROM actor; /* ollama */',
  columns: [{ name: 'count', type: 'bigint' }],
  rows: [[200]],
  row_count: 1,
  attempt_number: 1,
  is_last_auto_retry: false,
};

const GEMINI_RESULT: QueryResult = {
  kind: 'result',
  attempt_id: 'attempt-gemini-1',
  question: 'How many actors?',
  generated_sql: 'SELECT count(*) FROM actor; /* gemini */',
  columns: [{ name: 'count', type: 'bigint' }],
  rows: [[200]],
  row_count: 1,
  attempt_number: 1,
  is_last_auto_retry: false,
};

test.describe('T-178: provider-switch (Phase 1 — mocked)', () => {
  test('submit with ollama → accept → switch mock to gemini → history persists old + new query works', async ({ page }) => {
    let currentProvider = 'ollama';

    // Mock /query/submit with provider-aware response
    await page.route('**/query/submit', async (route: Route) => {
      const body = currentProvider === 'ollama' ? OLLAMA_RESULT : GEMINI_RESULT;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    });

    // Mock /query/accept
    let acceptCount = 0;
    await page.route('**/query/accept', async (route: Route) => {
      acceptCount++;
      const body: AcceptedQuerySummary = {
        id: `query-${acceptCount}`,
        question_text: 'How many actors?',
        generated_sql: currentProvider === 'ollama' ? OLLAMA_RESULT.generated_sql : GEMINI_RESULT.generated_sql,
        accepted_at: new Date().toISOString(),
      };
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(body) });
    });

    // Mock /history list
    await page.route(/\/history(?:\?.*)?$/, async (route: Route) => {
      const items: AcceptedQuerySummary[] = [];
      if (acceptCount >= 1) {
        items.push({
          id: 'query-1',
          question_text: 'How many actors?',
          generated_sql: OLLAMA_RESULT.generated_sql,
          accepted_at: new Date().toISOString(),
        });
      }
      if (acceptCount >= 2) {
        items.push({
          id: 'query-2',
          question_text: 'How many actors?',
          generated_sql: GEMINI_RESULT.generated_sql,
          accepted_at: new Date().toISOString(),
        });
      }
      const body: HistoryListResponse = { items, total: items.length, next_cursor: null };
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    });

    // Mock /history/{id} detail
    await page.route('**/history/*', async (route: Route) => {
      const url = new URL(route.request().url());
      const id = url.pathname.split('/').pop();
      if (id === 'query-1') {
        const body: AcceptedQueryDetail = {
          id: 'query-1',
          question_text: 'How many actors?',
          generated_sql: OLLAMA_RESULT.generated_sql,
          llm_provider: 'ollama',
          accepted_at: new Date().toISOString(),
          database_connection_id: 'conn-1',
        };
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
        return;
      }
      if (id === 'query-2') {
        const body: AcceptedQueryDetail = {
          id: 'query-2',
          question_text: 'How many actors?',
          generated_sql: GEMINI_RESULT.generated_sql,
          llm_provider: 'gemini',
          accepted_at: new Date().toISOString(),
          database_connection_id: 'conn-1',
        };
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
        return;
      }
      await route.fallback();
    });

    // Step 1: sign in and submit with ollama
    await signIn(page);
    await page.goto('/ask');
    await expect(page).toHaveURL(/\/ask/);
    await expect(page.locator('textarea')).toBeEnabled({ timeout: 5_000 });

    await page.getByPlaceholder(/Ask a question/i).fill('How many actors?');
    await page.getByRole('button', { name: /ask/i }).click();
    await expect(page.getByRole('table')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/ollama/)).toBeVisible();
    await page.getByRole('button', { name: /^accept$/i }).click();
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 5_000 });

    // Step 2: switch provider to gemini (simulated by changing mock state)
    currentProvider = 'gemini';

    // Step 3: submit with gemini
    await page.getByPlaceholder(/Ask a question/i).fill('How many actors?');
    await page.getByRole('button', { name: /ask/i }).click();
    await expect(page.getByRole('table')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/gemini/)).toBeVisible();
    await page.getByRole('button', { name: /^accept$/i }).click();
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 5_000 });

    // Step 4: navigate to history and assert both queries are present
    await page.getByTestId('sidebar-nav-history').click();
    await expect(page).toHaveURL(/\/history/);
    await expect(page.getByText(/ollama/)).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/gemini/)).toBeVisible({ timeout: 5_000 });

    // Step 5: open ollama query detail and assert provider label
    await page.getByText(/ollama/).click();
    await expect(page.getByText('ollama')).toBeVisible();
  });
});

test.describe('T-178: provider-switch (Phase 2 — full-stack, deferred)', () => {
  test.skip('full-stack provider switch with real docker', async ({ page }) => {
    /**
     * Unskip once T-231 (docker-in-CI) lands.
     *
     * Steps:
     * 1. Start docker-compose.dev.yml with LLM_PROVIDER=ollama.
     * 2. Sign in, submit + accept a query.
     * 3. Restart the backend container with LLM_PROVIDER=openai.
     * 4. Navigate to /history and assert the previously accepted query is visible.
     * 5. Submit a new question and assert it succeeds (routes to OpenAI adapter).
     */
    await page.goto('/');
    throw new Error('Phase 2 not yet implemented — unskip after T-231');
  });
});
