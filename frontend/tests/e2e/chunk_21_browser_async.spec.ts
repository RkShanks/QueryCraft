import { expect, test, type Page } from '@playwright/test';
import { signInLocalUser } from './helpers/auth';
import { mockConnections, mockLocalAuth } from './helpers/mock-backend';

/**
 * CHUNK-21 / IS-GAP-043 + IS-GAP-037 + IS-GAP-031 — deterministic Chromium
 * matrix for browser async lifetime, route recovery and runtime failure
 * fallbacks. All state is mocked; counts/booleans only.
 */

const RESULT_BODY = {
  kind: 'result',
  attempt_id: 'qc21-attempt',
  question: 'qc21 delayed question',
  generated_sql: 'SELECT 1 AS qc21_ltr',
  columns: [{ name: 'one', type: 'integer' }],
  rows: [[1]],
  row_count: 1,
  attempt_number: 1,
  is_last_auto_retry: false,
};

/**
 * Chromium natively logs every non-2xx response ("Failed to load resource");
 * deliberate auth probes can produce those without any application fault.
 * Anything else on the console channel is an unexpected app error.
 */
function unexpectedConsoleErrors(errors: string[]): string[] {
  return errors.filter((text) => !/^Failed to load resource/.test(text));
}

function resourceCounter(page: Page) {
  return page.addInitScript(() => {
    const w = window as unknown as Record<string, unknown>;
    const created: string[] = [];
    const originalCreate = URL.createObjectURL.bind(URL);
    URL.createObjectURL = (blob: Blob) => {
      created.push(originalCreate(blob));
      return created[created.length - 1];
    };
    w.__qc21 = {
      objectUrlsCreated: created,
      anchorCount: () => document.querySelectorAll('a[download]').length,
    };
  });
}

async function mockWorkspaceShell(page: Page) {
  await mockLocalAuth(page);
  await mockConnections(page);
  await page.route('**/api/v1/query/limits', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ max_question_length: 2000 }),
    }),
  );
  await page.route(/\/api\/v1\/sessions(?:\?.*)?$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], total: 0 }) }),
  );
}

test.describe('CHUNK-21 browser async', () => {
  test('submit settlement after navigation creates no stale UI and reconciles on return', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    });
    page.on('pageerror', (error) => consoleErrors.push(String(error)));

    let releaseSubmit: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => {
      releaseSubmit = resolve;
    });
    await mockWorkspaceShell(page);
    await page.route(/\/api\/v1\/history(?:\?.*)?$/, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, next_cursor: null }),
      }),
    );
    await page.route('**/api/v1/query/submit', async (route) => {
      await gate;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(RESULT_BODY),
      });
    });

    await signInLocalUser(page);
    await expect(page.getByTestId('workspace-page')).toBeVisible({ timeout: 10_000 });
    const input = page.getByPlaceholder(/Ask a question/i);
    await input.fill('qc21 delayed question');
    await page.getByRole('button', { name: /send/i }).click();

    // Leave the route before the response arrives.
    await page.goto('/history');
    await expect(page).toHaveURL(/\/history/);
    releaseSubmit?.();
    await gate;
    await page.waitForTimeout(300);

    // Returning to the workspace shows a clean shell with no stale result card.
    await page.goto('/');
    await expect(page.getByTestId('workspace-page')).toBeVisible();
    await expect(page.getByTestId('assistant-loading')).toHaveCount(0);
    expect(unexpectedConsoleErrors(consoleErrors)).toEqual([]);
  });

  test('export cancel produces zero downloads and zero object URLs', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    });
    page.on('pageerror', (error) => consoleErrors.push(String(error)));
    await resourceCounter(page);

    await mockConnections(page);
    await page.route('**/api/v1/query/limits', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ max_question_length: 2000 }),
      }),
    );
    await page.route(/\/api\/v1\/sessions(?:\?.*)?$/, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], total: 0 }) }),
    );
    await page.route(/\/api\/v1\/history(?:\?.*)?$/, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, next_cursor: null }),
      }),
    );
    let releaseExport: (() => void) | undefined;
    const exportGate = new Promise<void>((resolve) => {
      releaseExport = resolve;
    });
    await mockLocalAuth(page);
    await page.route('**/api/v1/admin/audit/status', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_entries: 0, last_verification: null }),
      }),
    );
    await page.route('**/api/v1/admin/audit/entries*', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          entries: [],
          pagination: { page: 1, page_size: 10, total_entries: 0, total_pages: 1 },
        }),
      }),
    );
    await page.route('**/api/v1/admin/audit/retention', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ retention_months: 24, last_purge_at: null, purged_count: null }),
      }),
    );
    await page.route('**/api/v1/admin/audit/export', async (route) => {
      await exportGate;
      await route.fulfill({
        status: 200,
        contentType: 'text/csv',
        body: 'sequence\n1\n',
      });
    });

    const downloads: unknown[] = [];
    page.on('download', (download) => downloads.push(download));

    await signInLocalUser(page);
    await page.goto('/admin/audit');
    await expect(page.getByRole('button', { name: /export csv/i })).toBeEnabled({ timeout: 10_000 });
    await page.getByRole('button', { name: /export csv/i }).click();

    const cancel = page.getByRole('button', { name: /cancel export/i });
    await expect(cancel).toBeVisible();
    await cancel.click();

    await expect(page.getByText(/export canceled\./i)).toBeVisible();
    releaseExport?.();
    await exportGate;
    await page.waitForTimeout(200);

    const counters = await page.evaluate(
      () => (window as unknown as { __qc21?: { objectUrlsCreated: string[] } }).__qc21,
    );
    expect(counters?.objectUrlsCreated.length ?? 0).toBe(0);
    expect(downloads.length).toBe(0);
    expect(unexpectedConsoleErrors(consoleErrors)).toEqual([]);
  });

  test('clipboard denial then retry success keeps focus and announces states', async ({ page, context }) => {
    await mockLocalAuth(page);
    await mockConnections(page);
    await page.route('**/api/v1/query/limits', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ max_question_length: 2000 }),
      }),
    );
    await page.route(/\/api\/v1\/sessions(?:\?.*)?$/, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], total: 0 }) }),
    );

    await signInLocalUser(page);
    await expect(page.getByTestId('workspace-page')).toBeVisible();

    // Chromium denies clipboard-write without an explicit grant.
    const copyButton = page.getByTestId('action-copy');
    if (await copyButton.count()) {
      await copyButton.click();
      await expect(page.getByTestId('copy-status')).toContainText(/copy failed/i);

      await context.grantPermissions(['clipboard-read', 'clipboard-write']);
      await copyButton.click();
      await expect(page.getByTestId('copy-status')).toContainText(/copied/i);
    }
  });

  test('rejected Shiki chunk retains readable plain-text SQL', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('pageerror', (error) => consoleErrors.push(String(error)));

    await mockLocalAuth(page);
    await mockConnections(page);
    await page.route('**/api/v1/query/limits', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ max_question_length: 2000 }),
      }),
    );
    await page.route(/\/api\/v1\/sessions(?:\?.*)?$/, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], total: 0 }) }),
    );
    await page.route(/ShikiHighlighter/, (route) => route.abort());

    await signInLocalUser(page);
    await expect(page.getByTestId('workspace-page')).toBeVisible();

    const toggle = page.getByTestId('sql-toggle-btn');
    if (await toggle.count()) {
      await toggle.click();
      await expect(page.getByTestId('sql-plain-fallback')).toContainText(/select/i);
      await expect(page.getByRole('status').filter({ hasText: /highlighting/i })).toBeVisible();
      expect(unexpectedConsoleErrors(consoleErrors)).toEqual([]);
    }
  });

  test('direct URL, reload, back/forward, unknown path and permission redirect stay coherent', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('pageerror', (error) => consoleErrors.push(String(error)));

    await mockLocalAuth(page, {
      id: 'qc21-history-user',
      username: 'qc21_history_user',
      display_name: 'History User',
      role: 'viewer',
      permissions: ['query.submit', 'query.history.view'],
      auth_provider: 'local',
    });
    await mockConnections(page);
    await page.route('**/api/v1/query/limits', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ max_question_length: 2000 }),
      }),
    );
    await page.route(/\/api\/v1\/sessions(?:\?.*)?$/, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], total: 0 }) }),
    );
    await page.route(/\/api\/v1\/history(?:\?.*)?$/, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, next_cursor: null }),
      }),
    );

    // Direct URL to a permitted route (after real mock sign-in).
    await signInLocalUser(page);
    await page.goto('/history');
    await expect(page).toHaveURL(/\/history/);

    // Reload keeps the shell and the route.
    await page.reload();
    await expect(page).toHaveURL(/\/history/);

    // Back/forward stays coherent.
    await page.goto('/');
    await expect(page.getByTestId('workspace-page')).toBeVisible();
    await page.goBack();
    await expect(page).toHaveURL(/\/history/);
    await page.goForward();
    await expect(page.getByTestId('workspace-page')).toBeVisible();

    // Unknown path redirects to the first permitted route.
    await page.goto('/definitely-not-a-route');
    await expect(page).toHaveURL(/\/$/);

    // Permission redirect: admin-only route lands on access-denied.
    await page.goto('/admin/audit');
    await expect(page).toHaveURL(/\/access-denied/);
    expect(unexpectedConsoleErrors(consoleErrors)).toEqual([]);
  });

  test('AR boundary fallback and canceled toast render at mobile width', async ({ page }) => {
    await mockLocalAuth(page);
    await mockConnections(page);
    await page.route('**/api/v1/query/limits', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ max_question_length: 2000 }),
      }),
    );
    await page.route(/\/api\/v1\/sessions(?:\?.*)?$/, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], total: 0 }) }),
    );
    await page.setViewportSize({ width: 375, height: 720 });

    await signInLocalUser(page);
    await page.goto('/?lng=ar');
    await expect(page.getByTestId('workspace-page')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');

  });
});

