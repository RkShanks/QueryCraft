import { test, expect } from '@playwright/test';

const USERNAME = process.env.E2E_TEST_USERNAME ?? 'e2e_user';
const PASSWORD = process.env.E2E_TEST_PASSWORD ?? 'e2e_password_123';

test.describe('US-1: sign-in → ask → history', () => {
  test('full happy path against real backend', async ({ page }) => {
    // Step 1: Sign in.
    await page.goto('/');
    await expect(page).toHaveURL(/\/sign-in/, { timeout: 5_000 });

    await page.getByLabel(/username/i).fill(USERNAME);
    await page.getByLabel(/password/i).fill(PASSWORD);
    await page.getByRole('button', { name: /sign\s*in/i }).click({ force: true });

    // Land on the main workspace page.
    await expect(page).toHaveURL(/\/(ask)?\/?$/);

    // Step 2: Submit a question about a valid Pagila table (e.g., customer)
    const question = 'How many customers are in the system?';
    await page.getByPlaceholder(/Ask a question/i).fill(question);
    
    // Click the "Send" button (since it's a chat interface now)
    await page.getByRole('button', { name: /send/i }).click({ force: true });

    // Wait for the assistant response card or result table to render.
    await expect(page.getByTestId('assistant-response-card')).toBeVisible({ timeout: 15_000 });

    // Step 3: Navigate to history.
    await page.getByRole('button', { name: /history/i }).click({ force: true });
    await expect(page).toHaveURL(/\/history/);

    // The query should automatically appear in the history list.
    await expect(page.getByText(question, { exact: false }).first()).toBeVisible({ timeout: 5_000 });
  });
});
