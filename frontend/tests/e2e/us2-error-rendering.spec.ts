/**
 * E2E spec for US-2 error-state rendering (evaluator rejection, timeout, concurrent).
 *
 * MOCKED at Playwright level (page.route). The backend state machine
 * lives on phase1-us2-be-routers, which integrates with FE at Chunk 3.8.
 *
 * After Wave 3 PR merges, this spec can be upgraded to full-stack E2E by:
 * 1. Removing the page.route() calls below.
 * 2. Configuring the StubLLM to return specific SQL that triggers each error.
 *
 * That upgrade happens in Chunk 3.9 (Gemini end-of-wave testing).
 */

import { test, expect, type Page } from '@playwright/test';
import { mockSubmitEvaluatorRejected, mockSubmitTimeout, mockSubmitConcurrent } from './helpers/mock-backend';

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

test.describe('US-2: error-state rendering', () => {
  test('evaluator rejection shows EvaluatorRejectionBanner', async ({ page }) => {
    await mockSubmitEvaluatorRejected(page);
    await signIn(page);

    await page.getByPlaceholder(/Ask a question/i).fill('Something unsafe?');
    await page.getByRole('button', { name: /^ask$/i }).click();

    // The evaluator-rejection banner should appear inside main
    const banner = page.locator('main').getByRole('alert');
    await expect(banner).toBeVisible({ timeout: 5_000 });
    await expect(banner).toContainText(/rejected for safety/i);
  });

  test('timeout shows TimeoutBanner with retry CTA', async ({ page }) => {
    await mockSubmitTimeout(page);
    await signIn(page);

    await page.getByPlaceholder(/Ask a question/i).fill('Slow query?');
    await page.getByRole('button', { name: /^ask$/i }).click();

    const banner = page.locator('main').getByRole('alert');
    await expect(banner).toBeVisible({ timeout: 5_000 });
    await expect(banner).toContainText(/took too long/i);
    await expect(page.getByRole('button', { name: /try again/i })).toBeVisible();
  });

  test('concurrent submission shows error toast', async ({ page }) => {
    await mockSubmitConcurrent(page);
    await signIn(page);

    await page.getByPlaceholder(/Ask a question/i).fill('Concurrent?');
    await page.getByRole('button', { name: /^ask$/i }).click();

    // The fixed toast alert at the top of the page
    const toast = page.locator('div[role="alert"]').filter({ hasText: /already being processed/i });
    await expect(toast).toBeVisible({ timeout: 5_000 });
  });
});
