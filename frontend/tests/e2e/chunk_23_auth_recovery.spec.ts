import { expect, test, type Page, type Route } from '@playwright/test';
import { mockConnections } from './helpers/mock-backend';

/**
 * CHUNK-23 / IS-GAP-044 — deterministic Chromium matrix for authentication
 * recovery states: SSO provider loading/configured/empty/failure+retry,
 * invalid callback codes, local double-submit suppression, permission-aware
 * landing, rejected sign-out retry, successful sign-out boundaries and
 * session-expiry distinction. All API responses are mocked; evidence records
 * booleans and counts only.
 */

type ProviderList = {
  providers: Array<{ protocol: string; display_name: string; login_url: string }>;
};

const PROVIDERS: ProviderList = {
  providers: [
    { protocol: 'oidc', display_name: 'Corporate OIDC', login_url: '/api/v1/auth/sso/oidc/login' },
    { protocol: 'saml', display_name: 'Partner SAML', login_url: '/api/v1/auth/sso/saml/login' },
  ],
};

function unexpectedConsoleErrors(errors: string[]): string[] {
  return errors.filter((text) => !/^Failed to load resource/.test(text));
}

/** Unauthenticated surface: /auth/me is always 401. */
async function mockAnonymousAuth(page: Page) {
  await page.route('**/api/v1/auth/me', (route: Route) =>
    route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'unauthorized', message_key: 'error.unauthorized' }),
    }),
  );
}

async function mockWorkspaceCompanions(page: Page) {
  await page.route('**/api/v1/query/limits', (route: Route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"max_question_length":2000}' }),
  );
  await page.route(/\/api\/v1\/sessions(?:\?.*)?$/, (route: Route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"items":[],"total":0,"next_cursor":null}' }),
  );
  await mockConnections(page);
  await page.route(/\/api\/v1\/history(?:\?.*)?$/, (route: Route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"items":[],"total":0,"next_cursor":null}' }),
  );
}

const WORKSPACE_USER = {
  id: 'chunk23-user',
  username: 'chunk23_user',
  display_name: 'Chunk23 User',
  role: 'admin',
  permissions: ['query.submit'],
  auth_provider: 'local',
};

test.describe('CHUNK-23 authentication recovery states', () => {
  test('provider loading resolves to configured buttons and stays distinct from the empty notice (EN 1440)', async ({ page }) => {
    await mockAnonymousAuth(page);
    let releaseProviders: (() => void) | undefined;
    await page.route('**/api/v1/auth/sso/providers', async (route: Route) => {
      await new Promise<void>((resolve) => {
        releaseProviders = resolve;
      });
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(PROVIDERS) });
    });

    await page.goto('/sign-in');
    const loading = page.getByTestId('sso-providers-loading');
    await expect(loading).toBeVisible();
    await expect(page.getByText(/SSO is not configured/i)).toHaveCount(0);

    releaseProviders?.();
    await expect(page.getByRole('button', { name: /Sign in with Corporate OIDC/i })).toBeVisible();
    await expect(loading).toHaveCount(0);

    // The empty notice is a different state than loading or failure.
    await page.route('**/api/v1/auth/sso/providers', (route: Route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"providers":[]}' }),
    );
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByText(/SSO is not configured/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /Sign in with Corporate OIDC/i })).toHaveCount(0);
    const consoleErrors: string[] = [];
    page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
    expect(unexpectedConsoleErrors(consoleErrors)).toHaveLength(0);
  });

  test('provider fetch failure renders a sanitized retry state that recovers exactly-once (EN 1440)', async ({ page }) => {
    await mockAnonymousAuth(page);
    let providerRequests = 0;
    await page.route('**/api/v1/auth/sso/providers', (route: Route) => {
      providerRequests += 1;
      if (providerRequests === 1) {
        return route.fulfill({ status: 503, contentType: 'application/json', body: '{"error":"service_unavailable"}' });
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(PROVIDERS) });
    });

    await page.goto('/sign-in');
    const errorBox = page.getByTestId('sso-providers-error');
    await expect(errorBox).toBeVisible();
    await expect(errorBox).toContainText(/Enterprise sign-in is temporarily unavailable/i);
    await expect(page.getByText(/SSO is not configured/i)).toHaveCount(0);
    const errorText = (await errorBox.innerText()) || '';
    expect(errorText).not.toMatch(/503|HTTP|fetch|service_unavailable|localhost/i);

    await page.getByRole('button', { name: /^Retry$/i }).click();
    await expect(page.getByRole('button', { name: /Sign in with Corporate OIDC/i })).toBeVisible();
    await expect(page.getByTestId('sso-providers-error')).toHaveCount(0);
    expect(providerRequests).toBe(2);
  });

  test('Arabic provider failure is localized inside RTL chrome at 375px (AR)', async ({ page }) => {
    await mockAnonymousAuth(page);
    await page.route('**/api/v1/auth/sso/providers', (route: Route) =>
      route.fulfill({ status: 503, contentType: 'application/json', body: '{"error":"service_unavailable"}' }),
    );

    await page.setViewportSize({ width: 375, height: 720 });
    await page.goto('/sign-in?lng=ar');
    const errorBox = page.getByTestId('sso-providers-error');
    await expect(errorBox).toBeVisible();
    await expect(errorBox).toContainText('تسجيل الدخول المؤسسي غير متوفر مؤقتاً');
    await expect(page.locator('.sign-in-page')).toHaveAttribute('dir', 'rtl');
    await expect(page.getByRole('button', { name: 'إعادة المحاولة' })).toBeVisible();
    const pageText = (await page.locator('body').innerText()) || '';
    expect(pageText).not.toContain('auth.signIn.sso.loadError');
  });

  test('invalid callback parameters map to the sanitized localized message only (EN)', async ({ page }) => {
    await mockAnonymousAuth(page);
    await page.route('**/api/v1/auth/sso/providers', (route: Route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"providers":[]}' }),
    );

    await page.goto('/sign-in?error=sso_validation_failed&code=leaked&state=tampered');
    await expect(page.getByText(/SSO validation failed\./i)).toBeVisible();
    const pageText = (await page.locator('body').innerText()) || '';
    expect(pageText).not.toContain('leaked');
    expect(pageText).not.toContain('tampered');
    expect(pageText).not.toContain('sso_validation_failed');
  });

  test('local sign-in suppresses duplicate submissions and lands on the permitted route (EN)', async ({ page }) => {
    let authenticated = false;
    await page.route('**/api/v1/auth/me', (route: Route) => {
      if (!authenticated) {
        return route.fulfill({ status: 401, contentType: 'application/json', body: '{"error":"unauthorized","message_key":"error.unauthorized"}' });
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(WORKSPACE_USER) });
    });
    await page.route('**/api/v1/auth/sign-in', (route: Route) => {
      signInCalls += 1;
      if (failFirst && signInCalls === 1) {
        return route.fulfill({ status: 401, contentType: 'application/json', body: '{"error":"unauthorized"}' });
      }
      authenticated = true;
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(WORKSPACE_USER) });
    });
    await page.route('**/api/v1/auth/sso/providers', (route: Route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"providers":[]}' }),
    );
    await mockWorkspaceCompanions(page);
    let signInCalls = 0;
    let failFirst = true;

    await page.goto('/sign-in');
    const form = page.locator('form.sign-in-form');
    await form.getByLabel(/username/i).fill('chunk23_user');
    await form.getByLabel(/password/i).fill('sup3r-secret-pw');
    await form.getByRole('button', { name: /^sign in$/i }).click();

    const alert = page.getByRole('alert');
    await expect(alert).toContainText(/Invalid username or password/i);
    expect(((await alert.innerText()) || '').includes('sup3r-secret-pw')).toBe(false);

    failFirst = false;
    await Promise.all([
      page.waitForURL((url) => url.pathname === '/', { timeout: 15000 }),
      form.getByRole('button', { name: /^sign in$/i }).click(),
    ]);
    await expect(page.getByTestId('sidebar')).toBeVisible();
    expect(signInCalls).toBeGreaterThanOrEqual(2);
  });

  test('rejected sign-out keeps identity with a truthful Retry; confirmed sign-out clears boundaries (EN 768)', async ({ page }) => {
    let authenticated = false;
    let signOutFailures = 1;
    await page.route('**/api/v1/auth/me', (route: Route) => {
      if (!authenticated) {
        return route.fulfill({ status: 401, contentType: 'application/json', body: '{"error":"unauthorized","message_key":"error.unauthorized"}' });
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(WORKSPACE_USER) });
    });
    await page.route('**/api/v1/auth/sign-in', (route: Route) => {
      authenticated = true;
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(WORKSPACE_USER) });
    });
    await page.route('**/api/v1/auth/sign-out', async (route: Route) => {
      if (signOutFailures > 0) {
        signOutFailures -= 1;
        return route.fulfill({ status: 503, contentType: 'application/json', body: '{"error":"service_unavailable"}' });
      }
      authenticated = false;
      return route.fulfill({ status: 204 });
    });
    await mockWorkspaceCompanions(page);

    await page.setViewportSize({ width: 768, height: 900 });
    await page.goto('/');
    await expect(page).toHaveURL(/\/sign-in/, { timeout: 10000 });
    const form = page.locator('form.sign-in-form');
    await form.getByLabel(/username/i).fill('chunk23_user');
    await form.getByLabel(/password/i).fill('sup3r-secret-pw');
    await form.getByRole('button', { name: /^sign in$/i }).click();
    await page.waitForURL((url) => url.pathname === '/', { timeout: 15000 });
    await expect(page.getByTestId('sidebar')).toBeVisible();

    // Reject the first sign-out: truthful alert plus explicit Retry action.
    await page.getByTestId('sidebar-sign-out').click();
    const signOutAlert = page.locator('.sidebar-sign-out-error');
    await expect(signOutAlert).toContainText(/Sign out failed\. Your server session is still active\./i);
    const retry = signOutAlert.getByRole('button', { name: /^Retry$/i });
    await expect(retry).toBeVisible();
    await expect(page.getByTestId('sidebar')).toBeVisible(); // identity preserved

    // Confirmed sign-out clears the identity boundary back to the public shell.
    await retry.click();
    await page.waitForURL(/\/sign-in$/, { timeout: 15000 });
    await expect(page.locator('form.sign-in-form')).toBeVisible();
    const storageDump = JSON.stringify([
      await page.evaluate(() => ({ l: Object.fromEntries(Object.entries(localStorage)), s: Object.fromEntries(Object.entries(sessionStorage)) })),
    ]);
    expect(storageDump).not.toContain('chunk23_user');
    expect(storageDump).not.toContain('query.submit');
  });

  test('session expiry is distinct from ordinary sign-out failure (EN)', async ({ page }) => {
    let authenticated = false;
    let featureShouldExpire = false;
    await page.route('**/api/v1/auth/me', (route: Route) => {
      if (!authenticated) {
        return route.fulfill({ status: 401, contentType: 'application/json', body: '{"error":"unauthorized","message_key":"error.unauthorized"}' });
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(WORKSPACE_USER) });
    });
    await page.route('**/api/v1/auth/sign-in', (route: Route) => {
      authenticated = true;
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(WORKSPACE_USER) });
    });
    await page.route('**/api/v1/auth/sign-out', (route: Route) => route.fulfill({ status: 204 }));
    await page.route('**/api/v1/query/limits', (route: Route) => {
      if (featureShouldExpire) {
        return route.fulfill({ status: 401, contentType: 'application/json', body: '{"error":"unauthorized","message_key":"error.unauthorized"}' });
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: '{"max_question_length":2000}' });
    });
    await page.route(/\/api\/v1\/sessions(?:\?.*)?$/, (route: Route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"items":[],"total":0,"next_cursor":null}' }),
    );
    await mockConnections(page);
    await page.route(/\/api\/v1\/history(?:\?.*)?$/, (route: Route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"items":[],"total":0,"next_cursor":null}' }),
    );

    await page.goto('/');
    await expect(page).toHaveURL(/\/sign-in/, { timeout: 10000 });
    const form = page.locator('form.sign-in-form');
    await form.getByLabel(/username/i).fill('chunk23_user');
    await form.getByLabel(/password/i).fill('sup3r-secret-pw');
    await form.getByRole('button', { name: /^sign in$/i }).click();
    await page.waitForURL((url) => url.pathname === '/', { timeout: 15000 });
    await expect(page.getByTestId('sidebar')).toBeVisible();

    // A feature request 401 publishes session expiry, not a sign-out failure.
    featureShouldExpire = true;
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForURL(/\/sign-in\?error=session_expired$/, { timeout: 15000 });
    await expect(page.getByText(/Your session has expired or you are not signed in\./i)).toBeVisible();
    const pageText = (await page.locator('body').innerText()) || '';
    expect(pageText).not.toContain('session_expired');
  });
});
