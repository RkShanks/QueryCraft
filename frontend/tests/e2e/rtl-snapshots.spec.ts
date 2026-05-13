import { test, expect } from '@playwright/test';

test.describe('RTL visual snapshots', () => {
  test.beforeEach(async ({ page }) => {
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

    // Mock sessions list
    await page.route('**/sessions', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [
            {
              id: 'session-1',
              preview_text: 'How many users in the database?',
              created_at: new Date(Date.now() - 3600_000).toISOString(),
              last_activity_at: new Date().toISOString(),
            },
          ],
          total: 1,
        }),
      });
    });

    // Mock session detail
    await page.route('**/sessions/session-1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'session-1',
          preview_text: 'How many users?',
          created_at: new Date(Date.now() - 3600_000).toISOString(),
          last_activity_at: new Date().toISOString(),
          attempts: [
            {
              id: 'attempt-1',
              question_text: 'How many users?',
              generated_sql: 'SELECT COUNT(*) FROM users;',
              accepted_at: new Date().toISOString(),
              saved: true,
              feedback: 1,
            },
          ],
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
  });

  test('all components render correctly in LTR', async ({ page }) => {
    await page.addInitScript(() => {
      document.documentElement.setAttribute('dir', 'ltr');
      document.documentElement.setAttribute('lang', 'en');
    });

    // SettingsPage — covers AppShell + Sidebar + SettingsPage
    await page.goto('/settings');
    await expect(page.getByTestId('settings-page')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId('settings-llm-context-cap')).toBeVisible();
    await expect(page.getByTestId('settings-save-btn')).toBeVisible();

    // WorkspacePage — click session in sidebar to load conversation
    await page.goto('/');
    await expect(page.getByTestId('workspace-page')).toBeVisible({ timeout: 10_000 });

    // Click the session item to load conversation
    await page.getByTestId('session-item-session-1').click();
    await expect(page.getByTestId('assistant-response-card')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId('code-block-action-bar')).toBeVisible();
    await expect(page.getByTestId('response-feedback-bar')).toBeVisible();
    await expect(page.getByTestId('prompt-input')).toBeVisible();
  });

  test('all components render correctly in RTL', async ({ page }) => {
    await page.addInitScript(() => {
      document.documentElement.setAttribute('dir', 'rtl');
      document.documentElement.setAttribute('lang', 'ar');
    });

    // SettingsPage
    await page.goto('/settings');
    await expect(page.getByTestId('settings-page')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId('settings-llm-context-cap')).toBeVisible();

    // WorkspacePage with RTL session
    await page.goto('/');
    await expect(page.getByTestId('workspace-page')).toBeVisible({ timeout: 10_000 });
    await page.getByTestId('session-item-session-1').click();
    await expect(page.getByTestId('assistant-response-card')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId('code-block-action-bar')).toBeVisible();
    await expect(page.getByTestId('response-feedback-bar')).toBeVisible();
  });
});
