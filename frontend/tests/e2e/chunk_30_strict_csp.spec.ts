import { expect, test } from '@playwright/test';

const STRICT_SCRIPT_POLICY = "script-src 'self';";
type BrowserErrorCategory = 'console_error' | 'csp_violation' | 'page_error';

test.use({ screenshot: 'off', trace: 'off', video: 'off' });

test('CHUNK-30 production SPA mounts under strict CSP without runtime compilation', async ({
  page,
}) => {
  const browserErrorCategories = new Set<BrowserErrorCategory>();
  page.on('console', (message) => {
    if (message.type() !== 'error') return;
    browserErrorCategories.add(
      message.text().includes('Content Security Policy') ? 'csp_violation' : 'console_error'
    );
  });
  page.on('pageerror', () => browserErrorCategories.add('page_error'));

  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'unauthorized', message_key: 'error.unauthorized' }),
    })
  );
  await page.route('**/api/v1/auth/sso/providers', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ providers: [] }),
    })
  );

  const documentResponse = await page.goto('/sign-in?lng=en');
  const contentSecurityPolicy = documentResponse?.headers()['content-security-policy'] ?? '';

  expect(contentSecurityPolicy).toContain(STRICT_SCRIPT_POLICY);
  expect(contentSecurityPolicy).not.toContain('unsafe-eval');
  expect([...browserErrorCategories].sort()).toEqual([]);
  await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();
  await expect(page).toHaveTitle('Sign In | QueryCraft');
});
