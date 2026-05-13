import { test, expect } from '@playwright/test';

test.describe('RTL visual snapshots', () => {
  test('settings page renders correctly in LTR and RTL', async ({ page }) => {
    // Mock auth
    await page.route('**/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'test-user-id',
          username: 'admin',
          display_name: 'Admin User',
          role: 'admin',
        }),
      });
    });

    // Mock admin settings
    await page.route('**/admin/settings', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ llm_context_cap: 3 }),
      });
    });

    // LTR: set dir and lang
    await page.addInitScript(() => {
      document.documentElement.setAttribute('dir', 'ltr');
      document.documentElement.setAttribute('lang', 'en');
    });
    await page.goto('/settings');
    await expect(page.getByTestId('settings-page')).toBeVisible({ timeout: 5_000 });
    await expect(page.getByTestId('settings-llm-context-cap')).toBeVisible();
    await page.screenshot({ path: 'e2e-snapshots/settings-ltr.png', fullPage: true });

    // RTL: switch dir and lang via i18n
    await page.addInitScript(() => {
      document.documentElement.setAttribute('dir', 'rtl');
      document.documentElement.setAttribute('lang', 'ar');
    });
    await page.reload();
    await expect(page.getByTestId('settings-page')).toBeVisible({ timeout: 5_000 });
    await expect(page.getByTestId('settings-llm-context-cap')).toBeVisible();
    await page.screenshot({ path: 'e2e-snapshots/settings-rtl.png', fullPage: true });
  });
});
