import { test, expect } from '@playwright/test';
import { signInLocalUser } from './helpers/auth';
import { mockConnections, mockHistoryList, mockLocalAuth, mockSubmitCustom } from './helpers/mock-backend';

test.describe('US-1: sign-in → ask → history', () => {
  test('happy path from local sign-in through saved history', async ({ page }) => {
    const question = 'How many customers are in the system?';
    await mockLocalAuth(page);
    await mockConnections(page);
    await mockSubmitCustom(page, {
      kind: 'result',
      attempt_id: 'attempt-us1-customer-count',
      accepted_query_id: 'accepted-us1-customer-count',
      question,
      generated_sql: 'SELECT count(*) FROM customer;',
      columns: [{ name: 'count', type: 'bigint' }],
      rows: [[599]],
      row_count: 1,
      attempt_number: 1,
      is_last_auto_retry: false,
    });
    await mockHistoryList(page, {
      items: [
        {
          id: 'accepted-us1-customer-count',
          question_text: question,
          generated_sql: 'SELECT count(*) FROM customer;',
          accepted_at: new Date().toISOString(),
        },
      ],
      total: 1,
      next_cursor: null,
    });

    // Step 1: Sign in.
    await signInLocalUser(page);
    await expect(page.locator('textarea')).toBeEnabled({ timeout: 10_000 });
    await expect(page.getByTestId('database-selector-trigger')).toBeVisible({ timeout: 10_000 });

    // Step 2: Submit a question about a valid Pagila table (e.g., customer)
    const input = page.getByPlaceholder(/Ask a question/i);
    await input.fill(question);
    await expect(input).toHaveValue(question);
    
    // Click the "Send" button (since it's a chat interface now)
    await page.getByRole('button', { name: /send/i }).click({ force: true });

    // Wait for the assistant response card or result table to render.
    await expect(page.getByTestId('assistant-response-card')).toBeVisible({ timeout: 45_000 });
    await expect(page.getByRole('table')).toBeVisible({ timeout: 5_000 });

    // Step 3: Navigate to history.
    await page.getByRole('button', { name: /history/i }).click({ force: true });
    await expect(page).toHaveURL(/\/history/);

    // The query should automatically appear in the history list.
    await expect(page.getByText(question, { exact: false }).first()).toBeVisible({ timeout: 5_000 });
  });
});
