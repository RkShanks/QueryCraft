/**
 * E2E spec T-157: timeout displays message and writes no history.
 *
 * Scenario:
 *   - User enters a question → mocked backend returns 504 timeout.
 *   - UI surfaces the timeout banner with i18n message.
 *   - Result table is NOT shown.
 *   - History endpoint returns empty (no row written).
 *
 * MOCKED at Playwright level (page.route). After backend supports a
 * configurable short timeout in test mode, this can be upgraded to
 * full-stack E2E by removing the mocks.
 */

import { test, expect, type Page } from '@playwright/test';
import { mockSubmitTimeout, mockHistoryEmpty, mockConnections, mockLocalAuth } from './helpers/mock-backend';
import { signInLocalUser } from './helpers/auth';

async function signIn(page: Page) {
  await mockLocalAuth(page);
  await mockConnections(page);
  await signInLocalUser(page);
  await page.goto('/ask');
  await expect(page).toHaveURL(/\/ask/);
  await expect(page.locator('textarea')).toBeEnabled({ timeout: 5_000 });
}

test.describe('T-157: timeout displays message and writes no history', () => {
  test('slow query shows timeout banner, no result table, no history row', async ({ page }) => {
    await mockSubmitTimeout(page);
    await mockHistoryEmpty(page);
    await signIn(page);

    await page.getByPlaceholder(/Ask a question/i).fill('Slow query?');
    await page.getByRole('button', { name: /ask/i }).click();

    // Timeout banner should appear inside <main>
    const banner = page.locator('main').getByRole('alert');
    await expect(banner).toBeVisible({ timeout: 5_000 });
    await expect(banner).toContainText(/took too long/i);

    // Retry CTA should be visible
    await expect(page.getByRole('button', { name: /try again/i })).toBeVisible();

    // Result table must NOT appear
    await expect(page.getByRole('table')).not.toBeVisible();

    // Navigate to history and assert no new row was written
    await page.getByTestId('sidebar-nav-history').click();
    await expect(page).toHaveURL(/\/history/);
    await expect(page.getByText(/no history yet/i)).toBeVisible({ timeout: 5_000 });
  });
});
