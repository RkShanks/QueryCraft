import { expect, test, type ConsoleMessage, type Page, type Route } from '@playwright/test';

const STRICT_CSP = "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:";
const AUTHORIZED_CONNECTION_ID = '550e8400-e29b-41d4-a716-446655440031';
const BOOKMARK_QUESTION = 'Revenue & salary / Q3?';

type ApiMetrics = {
  authorizationRequests: number;
  featureRequests: string[];
  submitRequests: number;
};

function profile(permissions: string[]) {
  return {
    id: 'chunk-31-user',
    username: 'chunk-31-user',
    display_name: 'CHUNK-31 User',
    role: 'user',
    role_name: 'user',
    permissions,
    auth_provider: 'local',
  };
}

function json(body: unknown, status = 200) {
  return {
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  };
}

async function mockApi(page: Page, permissions: string[] | null): Promise<ApiMetrics> {
  const metrics: ApiMetrics = {
    authorizationRequests: 0,
    featureRequests: [],
    submitRequests: 0,
  };

  await page.route('**/api/v1/**', async (route: Route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      metrics.authorizationRequests += 1;
      await route.fulfill(
        permissions === null
          ? json({ error: 'unauthorized', message_key: 'error.unauthorized' }, 401)
          : json(profile(permissions))
      );
      return;
    }
    if (path === '/api/v1/auth/sso/providers') {
      await route.fulfill(json({ providers: [] }));
      return;
    }

    metrics.featureRequests.push(path);
    if (path === '/api/v1/sessions') {
      await route.fulfill(json({ items: [], total: 0, next_cursor: null }));
      return;
    }
    if (path === '/api/v1/connections') {
      await route.fulfill(json({
        connections: [{
          id: AUTHORIZED_CONNECTION_ID,
          display_name: 'Authorized database',
          database_type: 'postgresql',
        }],
      }));
      return;
    }
    if (path === '/api/v1/query/limits') {
      await route.fulfill(json({ max_question_length: 2000 }));
      return;
    }
    if (path === '/api/v1/query/submit') {
      metrics.submitRequests += 1;
    }
    await route.fulfill(json({}));
  });

  return metrics;
}

function observeBrowserErrors(page: Page) {
  const errors: string[] = [];
  page.on('console', (message: ConsoleMessage) => {
    if (message.type() !== 'error') return;
    const isExpectedUnauthorized =
      message.text().includes('status of 401') &&
      message.location().url.includes('/api/v1/auth/me');
    if (!isExpectedUnauthorized) errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(String(error)));
  return errors;
}

async function observeDocumentTitles(page: Page) {
  await page.addInitScript(() => {
    const titles: string[] = [];
    Object.assign(window, { __chunk31Titles: titles });
    new MutationObserver(() => titles.push(document.title)).observe(document, {
      subtree: true,
      childList: true,
      characterData: true,
    });
  });
}

async function expectNoLegacySurface(page: Page) {
  await expect(page.locator('.ask-question-page')).toHaveCount(0);
  await expect(page.locator('.query-input')).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText('documentTitle.');
  await expect.poll(() => page.evaluate(() => ({
    root: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    body: document.body.scrollWidth - document.body.clientWidth,
  }))).toEqual({ root: 0, body: 0 });
}

function expectStrictCsp(headers: Record<string, string>) {
  const policy = headers['content-security-policy'] ?? '';
  expect(policy).toBe(STRICT_CSP);
  expect(policy).not.toContain('unsafe-eval');
}

test.use({ screenshot: 'off', trace: 'off', video: 'off' });

const bookmarkCases = [
  { locale: 'en', direction: 'ltr', title: 'Workspace | QueryCraft', width: 1440, height: 900 },
  { locale: 'en', direction: 'ltr', title: 'Workspace | QueryCraft', width: 768, height: 1024 },
  { locale: 'en', direction: 'ltr', title: 'Workspace | QueryCraft', width: 375, height: 812 },
  { locale: 'ar', direction: 'rtl', title: 'مساحة العمل | QueryCraft', width: 1440, height: 900 },
  { locale: 'ar', direction: 'rtl', title: 'مساحة العمل | QueryCraft', width: 768, height: 1024 },
  { locale: 'ar', direction: 'rtl', title: 'مساحة العمل | QueryCraft', width: 375, height: 812 },
] as const;

for (const browserCase of bookmarkCases) {
  test(`CHUNK-31 ${browserCase.locale} ${browserCase.width}px bookmark settles on Workspace`, async ({ page }) => {
    await page.setViewportSize({ width: browserCase.width, height: browserCase.height });
    const errors = observeBrowserErrors(page);
    await observeDocumentTitles(page);
    const metrics = await mockApi(page, ['query.submit']);

    await page.goto('/');
    await expect(page.getByTestId('workspace-page')).toBeVisible();
    metrics.authorizationRequests = 0;
    metrics.featureRequests.length = 0;

    const bookmarkParams = new URLSearchParams({
      question: BOOKMARK_QUESTION,
      connectionId: AUTHORIZED_CONNECTION_ID,
      lng: browserCase.locale,
      unknown: 'discard-me',
    });
    const documentResponse = await page.goto(`/ask?${bookmarkParams}#discard-me`);

    expectStrictCsp(documentResponse?.headers() ?? {});
    await expect(page).toHaveURL(`/?lng=${browserCase.locale}`);
    await expect(page).toHaveTitle(browserCase.title);
    await expect(page.locator('html')).toHaveAttribute('lang', browserCase.locale);
    await expect(page.locator('html')).toHaveAttribute('dir', browserCase.direction);
    await expect(page.getByRole('textbox')).toHaveValue(BOOKMARK_QUESTION);
    await expect(page.getByText('Authorized database')).toBeVisible();
    await page.waitForLoadState('networkidle');

    expect(metrics.authorizationRequests).toBe(1);
    expect(metrics.submitRequests).toBe(0);
    expect(metrics.featureRequests.toSorted()).toEqual([
      '/api/v1/connections',
      '/api/v1/query/limits',
      '/api/v1/sessions',
    ]);
    const observedTitles = await page.evaluate(() =>
      (window as unknown as { __chunk31Titles: string[] }).__chunk31Titles
    );
    expect(observedTitles).not.toContain('Ask a Question | QueryCraft');
    expect(observedTitles).not.toContain('اطرح سؤالاً | QueryCraft');
    await expectNoLegacySurface(page);

    await page.goBack();
    await expect(page).toHaveURL(/\/$/);
    await expectNoLegacySurface(page);
    await page.goForward();
    await expect(page).toHaveURL(`/?lng=${browserCase.locale}`);
    await expectNoLegacySurface(page);
    await page.reload();
    await expect(page).toHaveURL(`/?lng=${browserCase.locale}`);
    await expect(page).toHaveTitle(browserCase.title);
    await expectNoLegacySurface(page);
    expect(errors).toEqual([]);
  });
}

test('CHUNK-31 unauthenticated bookmark reaches localized sign-in without feature requests', async ({ page }) => {
  const errors = observeBrowserErrors(page);
  const metrics = await mockApi(page, null);
  const response = await page.goto('/ask?question=sensitive&connectionId=discarded&lng=ar#legacy');

  expectStrictCsp(response?.headers() ?? {});
  await expect(page).toHaveURL('/sign-in?error=session_expired');
  await expect(page).toHaveTitle('تسجيل الدخول | QueryCraft');
  await expect(page.getByRole('heading', { name: 'تسجيل الدخول' })).toBeVisible();
  expect(metrics.authorizationRequests).toBe(1);
  expect(metrics.featureRequests).toEqual([]);
  expect(metrics.submitRequests).toBe(0);
  await expectNoLegacySurface(page);
  expect(errors).toEqual([]);
});

test('CHUNK-31 user without query.submit reaches localized access denied', async ({ page }) => {
  const errors = observeBrowserErrors(page);
  const metrics = await mockApi(page, ['query.history.view']);
  const response = await page.goto('/ask?question=sensitive&connectionId=discarded&lng=en#legacy');

  expectStrictCsp(response?.headers() ?? {});
  await expect(page).toHaveURL('/access-denied');
  await expect(page).toHaveTitle('Access Denied | QueryCraft');
  await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible();
  expect(metrics.authorizationRequests).toBe(1);
  expect(metrics.featureRequests).toEqual([]);
  expect(metrics.submitRequests).toBe(0);
  await expectNoLegacySurface(page);
  expect(errors).toEqual([]);
});
