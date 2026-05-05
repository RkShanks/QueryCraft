/**
 * E2E spec for US-2 double-reject → refine prompt → new question resets counter.
 *
 * MOCKED at Playwright level (page.route). The backend state machine
 * lives on phase1-us2-be-routers, which integrates with FE at Chunk 3.8.
 *
 * After Wave 3 PR merges, this spec can be upgraded to full-stack E2E by:
 * 1. Removing the page.route() calls below.
 * 2. The StubLLM in the integrated branch will support question-keyword lookups.
 *
 * That upgrade happens in Chunk 3.9 (Gemini end-of-wave testing).
 */

import { test, expect, type Page } from '@playwright/test';
import { mockSubmitSuccess, mockReject, mockSubmitCustom } from './helpers/mock-backend';

const USERNAME = process.env.E2E_TEST_USERNAME ?? 'e2e_user';
const PASSWORD = process.env.E2E_TEST_PASSWORD ?? 'e2e_password_123';

async function signIn(page: Page) {
  await page.goto('/');
  await expect(page).toHaveURL(/\/sign-in/, { timeout: 5_000 });
  await page.getByLabel(/username/i).fill(USERNAME);
  await page.getByLabel(/password/i).fill(PASSWORD);
  await page.getByRole('button', { name: /sign\s*in/i }).click();
  await expect(page).toHaveURL(/\/(ask)?\/?$/);
}

test.describe('US-2: double-reject → refine prompt → reset', () => {
  test('two rejections show refine banner; new question resets retry counter', async ({ page }) => {
    await mockSubmitSuccess(page);
    // first reject → result with last-auto-retry; second reject → refine prompt
    await mockReject(page, 'result', 1);

    // For the refined question, return a fresh result
    const refinedResult = {
      kind: 'result' as const,
      attempt_id: 'attempt-mock-refined',
      question: 'How many customers?',
      generated_sql: 'SELECT count(*) FROM customer;',
      columns: [{ name: 'count', type: 'bigint' }],
      rows: [[599]],
      row_count: 1,
      attempt_number: 1,
      is_last_auto_retry: false,
    };
    await mockSubmitCustom(page, refinedResult);

    await signIn(page);

    // Step 1: submit first question
    await page.getByPlaceholder(/Ask a question/i).fill('How many actors?');
    await page.getByRole('button', { name: /^ask$/i }).click();
    await expect(page.getByRole('table')).toBeVisible({ timeout: 5_000 });

    // Step 2: reject first result → auto-retry with last-retry indicator
    await page.getByRole('button', { name: /reject/i }).click();
    await expect(page.getByRole('table')).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/last auto retry/i)).toBeVisible();

    // Step 3: reject second result → refine prompt banner appears
    await page.getByRole('button', { name: /reject/i }).click();
    await expect(page.getByRole('alert').filter({ hasText: /refine/i })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByRole('button', { name: /try refining/i })).toBeVisible();

    // Step 4: click "Try Refining" → input clears, banners dismiss
    await page.getByRole('button', { name: /try refining/i }).click();
    await expect(page.getByRole('alert').filter({ hasText: /refine/i })).not.toBeVisible();
    await expect(page.getByPlaceholder(/Ask a question/i)).toHaveValue('');

    // Step 5: type a NEW question and submit → fresh result (counter reset)
    await page.getByPlaceholder(/Ask a question/i).fill('How many customers?');
    await page.getByRole('button', { name: /^ask$/i }).click();
    await expect(page.getByRole('table')).toBeVisible({ timeout: 5_000 });
    await expect(page.locator('.sql-display pre')).toContainText('SELECT count(*) FROM customer');

    // Fresh result should NOT show last-retry indicator (counter reset)
    await expect(page.getByText(/last auto retry/i)).not.toBeVisible();
  });
});
