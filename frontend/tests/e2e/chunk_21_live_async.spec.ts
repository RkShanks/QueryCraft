import { expect, test } from '@playwright/test';
import { signInLocalUser } from './helpers/auth';

/**
 * CHUNK-21 live boundary — real FastAPI HTTP without browser mocks.
 * Requires disposable runtime credentials (CHUNK20_LIVE_* style) via
 * E2E_ADMIN_USERNAME/E2E_ADMIN_PASSWORD against the isolated stack.
 */

const liveCredentialsConfigured = Boolean(
  process.env.E2E_ADMIN_PASSWORD ?? process.env.E2E_TEST_PASSWORD ?? process.env.ADMIN_PASSWORD,
);

test.skip(!liveCredentialsConfigured, 'CHUNK-21 disposable live credentials are required.');

/**
 * Chromium natively logs non-2xx transports; only application-level console
 * errors and page errors are unexpected for this boundary.
 */
function unexpectedConsoleErrors(errors: string[]): string[] {
  return errors.filter((text) => !/^Failed to load resource/.test(text));
}

test.describe('CHUNK-21 live async boundary', () => {
  test('unauthenticated deep link redirects to sign-in and authenticated reload keeps the route', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('pageerror', (error) => consoleErrors.push(String(error)));

    // Real 401 from the running API drives the AuthGuard redirect.
    await page.goto('/history');
    await expect(page).toHaveURL(/\/sign-in/, { timeout: 10_000 });

    await signInLocalUser(page);
    await expect(page.getByTestId('workspace-page')).toBeVisible({ timeout: 15_000 });

    // Direct URL + hard reload against the real backend keeps shell and route.
    await page.goto('/history');
    await expect(page).toHaveURL(/\/history/);
    await page.reload();
    await expect(page).toHaveURL(/\/history/);
    await expect(page.locator('main, [data-testid="workspace-page"]').first()).toBeVisible();

    // Unknown path lands on the first permitted route through real identity data.
    await page.goto('/not-a-real-route');
    await expect(page).toHaveURL(/\/(ask)?\/?$/);

    expect(unexpectedConsoleErrors(consoleErrors)).toEqual([]);
  });

  test('in-flight navigation leaves no stale settlement on the returned workspace', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    });
    page.on('pageerror', (error) => consoleErrors.push(String(error)));

    await signInLocalUser(page);
    await expect(page.getByTestId('workspace-page')).toBeVisible({ timeout: 15_000 });

    // Cross real network boundaries repeatedly; late responses must never
    // corrupt the new route's DOM or console channel.
    for (const path of ['/history', '/', '/history', '/']) {
      await page.goto(path);
      await page.waitForLoadState('networkidle');
    }
    await expect(page.getByTestId('workspace-page')).toBeVisible();
    await expect(page.getByTestId('assistant-loading')).toHaveCount(0);
    expect(unexpectedConsoleErrors(consoleErrors)).toEqual([]);
  });
});
