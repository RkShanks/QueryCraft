/**
 * E2E spec for US-2 reject → auto-retry → accept flow.
 *
 * MOCKED at Playwright level (page.route). The backend state machine
 * lives on phase1-us2-be-routers, which integrates with FE at Chunk 3.8.
 *
 * After Wave 3 PR merges, this spec can be upgraded to full-stack E2E by:
 * 1. Removing the page.route() calls below.
 * 2. Setting LLM_PROVIDER=stub (already default in docker-compose.dev.yml E2E mode).
 * 3. The StubLLM in the integrated branch will return deterministic SQL based on
 *    a question-keyword lookup, allowing assertions on real DB results from pagila.
 *
 * That upgrade happens in Chunk 3.9 (Gemini end-of-wave testing).
 */

import { test, expect, type Page } from '@playwright/test';
import { mockSubmitSuccess, mockReject, mockAccept, mockHistoryList } from './helpers/mock-backend';

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

test.describe('US-2: reject → auto-retry → accept', () => {
  test('rejecting first result triggers auto-retry, then accept persists to history', async ({ page }) => {
    await mockSubmitSuccess(page);
    await mockReject(page, 'result', 1); // first reject returns new result (last auto-retry)
    await mockAccept(page);
    await mockHistoryList(page);

    await signIn(page);

    // Step 1: submit a question
    await page.getByPlaceholder(/Ask a question/i).fill('How many actors?');
    await page.getByRole('button', { name: /^ask$/i }).click();

    // Step 2: first result appears
    await expect(page.getByRole('table')).toBeVisible({ timeout: 5_000 });
    await expect(page.locator('.sql-display pre')).toContainText('SELECT count(*) FROM actor');
    await expect(page.getByRole('button', { name: /reject/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /regenerate/i })).toBeVisible();

    // Step 3: click Reject → auto-retry result appears
    await page.getByRole('button', { name: /reject/i }).click();
    await expect(page.getByRole('table')).toBeVisible({ timeout: 5_000 });
    await expect(page.locator('.sql-display pre')).toContainText('customer'); // different SQL
    await expect(page.getByText(/last auto retry/i)).toBeVisible();

    // Step 4: click Accept → success alert
    await page.getByRole('button', { name: /^accept$/i }).click();
    await expect(page.getByRole('alert').filter({ hasText: /success/i })).toBeVisible({ timeout: 5_000 });

    // Step 5: navigate to history and verify accepted query
    await page.getByRole('link', { name: /history/i }).click();
    await expect(page).toHaveURL(/\/history/);
    await expect(page.getByText('How many actors?', { exact: false })).toBeVisible({ timeout: 5_000 });
  });
});
