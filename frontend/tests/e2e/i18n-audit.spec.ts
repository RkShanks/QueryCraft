import { test, expect, type Page } from '@playwright/test';

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

/**
 * Pattern that matches raw i18n keys like "history.column.timestamp"
 * — at least two dot-separated segments after the first segment.
 */
const MISSING_KEY_PATTERN = /(?<![a-zA-Z0-9])[a-z][a-zA-Z0-9_]+(?:\.[a-z][a-zA-Z0-9_]+){2,}(?![a-zA-Z0-9])/g;

async function assertNoMissingKeys(page: Page, url: string) {
  await page.goto(url);
  await page.waitForLoadState('networkidle');
  const bodyText = await page.locator('body').textContent() ?? '';
  const matches = bodyText.match(MISSING_KEY_PATTERN);
  if (matches && matches.length > 0) {
    throw new Error(`Missing i18n key: ${matches[0]}`);
  }
}

test.describe('T-185: no missing-key placeholders', () => {
  test('/sign-in has no raw i18n key strings', async ({ page }) => {
    await assertNoMissingKeys(page, '/sign-in');
  });

  test('/ (ask page) has no raw i18n key strings', async ({ page }) => {
    await signIn(page);
    await assertNoMissingKeys(page, '/');
  });

  test('/history has no raw i18n key strings', async ({ page }) => {
    await signIn(page);
    await assertNoMissingKeys(page, '/history');
  });
});

test.describe('T-186: no physical-direction CSS regression', () => {
  test('switching to RTL does not crash or error on /sign-in', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.goto('/sign-in');
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible();

    // Switch to RTL
    await page.evaluate(() => { document.documentElement.dir = 'rtl'; });
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible();

    // Switch back to LTR
    await page.evaluate(() => { document.documentElement.dir = 'ltr'; });
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible();

    expect(errors).toHaveLength(0);
  });

  test('switching to RTL does not crash or error on /history', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await signIn(page);
    await page.goto('/history');
    await expect(page.getByRole('heading', { name: /history/i })).toBeVisible();

    await page.evaluate(() => { document.documentElement.dir = 'rtl'; });
    await expect(page.getByRole('heading', { name: /history/i })).toBeVisible();

    await page.evaluate(() => { document.documentElement.dir = 'ltr'; });
    await expect(page.getByRole('heading', { name: /history/i })).toBeVisible();

    expect(errors).toHaveLength(0);
  });
});
