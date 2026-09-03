import { expect, test, type ConsoleMessage } from '@playwright/test';

const STRICT_CSP = "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:";
type BrowserErrorCategory = 'console_error' | 'csp_violation' | 'page_error';

function isExpectedAuthBootstrapError(message: ConsoleMessage): boolean {
  try {
    return (
      new URL(message.location().url).pathname === '/api/v1/auth/me' &&
      message.text().startsWith('Failed to load resource: the server responded with a status of 401')
    );
  } catch {
    return false;
  }
}

test.use({ screenshot: 'off', trace: 'off', video: 'off' });

for (const locale of [
  {
    direction: 'ltr',
    heading: 'Sign In',
    language: 'en',
    title: 'Sign In | QueryCraft',
    viewport: { height: 900, width: 1440 },
  },
  {
    direction: 'rtl',
    heading: 'تسجيل الدخول',
    language: 'ar',
    title: 'تسجيل الدخول | QueryCraft',
    viewport: { height: 812, width: 375 },
  },
]) {
  test(`CHUNK-30 ${locale.language} production SPA mounts under strict CSP`, async ({ page }) => {
    const browserErrorCategories = new Set<BrowserErrorCategory>();
    page.on('console', (message) => {
      if (message.type() !== 'error') return;
      if (isExpectedAuthBootstrapError(message)) return;
      browserErrorCategories.add(
        message.text().includes('Content Security Policy') ? 'csp_violation' : 'console_error'
      );
    });
    page.on('pageerror', () => browserErrorCategories.add('page_error'));
    await page.setViewportSize(locale.viewport);

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

    const documentResponse = await page.goto(`/sign-in?lng=${locale.language}`);
    const contentSecurityPolicy = documentResponse?.headers()['content-security-policy'] ?? '';

    expect(contentSecurityPolicy).toBe(STRICT_CSP);
    expect(contentSecurityPolicy).not.toContain('unsafe-eval');
    await expect(page.getByRole('heading', { name: locale.heading })).toBeVisible();
    await expect(page).toHaveTitle(locale.title);
    await expect(page.locator('html')).toHaveAttribute('lang', locale.language);
    await expect(page.locator('html')).toHaveAttribute('dir', locale.direction);
    await page.waitForLoadState('networkidle');
    expect([...browserErrorCategories].sort()).toEqual([]);
  });
}
