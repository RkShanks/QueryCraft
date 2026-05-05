import { test, expect } from '@playwright/test';

const USERNAME = process.env.E2E_TEST_USERNAME ?? 'e2e_user';
const PASSWORD = process.env.E2E_TEST_PASSWORD ?? 'e2e_password_123';

test.describe('US-1: sign-in → ask → accept → history', () => {
  test('full happy path against real backend', async ({ page }) => {
    // Step 1: Sign in.
    await page.goto('/');
    // AuthGuard shows spinner then redirects unauthenticated users
    await expect(page).toHaveURL(/\/sign-in/, { timeout: 5_000 });

    await page.getByLabel(/username/i).fill(USERNAME);
    await page.getByLabel(/password/i).fill(PASSWORD);
    await page.getByRole('button', { name: /sign\s*in/i }).click();

    // Land on the ask page.
    await expect(page).toHaveURL(/\/(ask)?\/?$/);

    // Step 2: Submit a question.
    const question = 'How many users are in the system?';
    await page.getByPlaceholder(/Ask a question/i).fill(question);
    await page.getByRole('button', { name: /^ask$/i }).click();

    // Wait for the result table to render.
    await expect(page.getByRole('table')).toBeVisible({ timeout: 10_000 });

    // Step 3: Accept the result.
    await page.getByRole('button', { name: /^accept$/i }).click();

    // Expect a success affordance (alert, toast, banner).
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 5_000 });

    // Step 4: Navigate to history.
    await page.getByRole('link', { name: /history/i }).click();
    await expect(page).toHaveURL(/\/history/);

    // The accepted query should appear in the history list.
    await expect(page.getByText(question, { exact: false })).toBeVisible({ timeout: 5_000 });
  });
});
