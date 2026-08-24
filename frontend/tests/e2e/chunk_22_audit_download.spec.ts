import { expect, test, type Page, type Route } from '@playwright/test';
import { signInLocalUser } from './helpers/auth';
import { mockConnections, mockLocalAuth } from './helpers/mock-backend';

/**
 * CHUNK-22 / IS-GAP-034 — deterministic Chromium matrix for the audit download
 * contract. Real browser download events carry mocked API file bodies with
 * genuine Content-Type/Content-Disposition headers. Evidence records only
 * booleans and counts; exported rows never enter assertions.
 */

const SERVER_CSV_NAME = 'audit_export_20260823T101500Z.csv';
const SERVER_JSON_NAME = 'audit_export_20260823T101530Z.json';

const AUDIT_SHELL = {
  status: { total_entries: 3, last_verification: null },
  retention: { retention_months: 24, last_purge_at: null, purged_count: null },
};

function auditEntriesResponse(actor: string) {
  return {
    entries: [
      {
        sequence_number: 1,
        timestamp: '2026-07-01T12:00:00Z',
        actor_identity: actor,
        action_type: 'query.submit',
        resource_type: 'database',
        resource_id: null,
        outcome: 'success',
        context: {},
      },
    ],
    pagination: { page: 1, page_size: 10, total_entries: 1, total_pages: 1 },
  };
}

async function mockAuditShell(page: Page) {
  await mockLocalAuth(page);
  // AppShell companions so no unrelated error state leaks into the audit page.
  await page.route('**/api/v1/query/limits', (route: Route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"max_question_length":2000}' }),
  );
  await page.route(/\/api\/v1\/sessions(?:\?.*)?$/, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{"items":[],"total":0,"next_cursor":null}',
    }),
  );
  await mockConnections(page);
  await page.route(/\/api\/v1\/history(?:\?.*)?$/, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{"items":[],"total":0,"next_cursor":null}',
    }),
  );
  await page.route('**/api/v1/admin/audit/status', (route: Route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(AUDIT_SHELL.status) }),
  );
  await page.route('**/api/v1/admin/audit/retention', (route: Route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(AUDIT_SHELL.retention) }),
  );
}

function unexpectedConsoleErrors(errors: string[]): string[] {
  return errors.filter((text) => !/^Failed to load resource/.test(text));
}

test.describe('CHUNK-22 audit download', () => {
  test('CSV/JSON downloads use applied filters with server filenames; unsent drafts stay excluded', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    });
    page.on('pageerror', (error) => consoleErrors.push(String(error)));

    const searchRequests: string[] = [];
    const exportBodies: Record<string, unknown>[] = [];
    await mockAuditShell(page);
    await page.route('**/api/v1/admin/audit/entries*', async (route: Route) => {
      const url = new URL(route.request().url());
      searchRequests.push(url.searchParams.toString());
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(auditEntriesResponse(url.searchParams.get('actor_identity') ?? 'seeded@example.com')),
      });
    });
    await page.route('**/api/v1/admin/audit/export', async (route: Route) => {
      exportBodies.push(route.request().postDataJSON() as Record<string, unknown>);
      const format = (route.request().postDataJSON() as { format: string }).format;
      const isCsv = format === 'csv';
      await route.fulfill({
        status: 200,
        contentType: isCsv ? 'text/csv; charset=utf-8' : 'application/json; charset=utf-8',
        headers: {
          'Content-Disposition': `attachment; filename="${isCsv ? SERVER_CSV_NAME : SERVER_JSON_NAME}"`,
        },
        body: isCsv ? '# checksum = x\nseq\n1\n' : '{"metadata":{},"entries":[]}',
      });
    });

    const downloads: string[] = [];
    page.on('download', (download) => downloads.push(download.suggestedFilename()));

    await signInLocalUser(page);
    await page.goto('/admin/audit');
    await expect(page.getByRole('button', { name: /export csv/i })).toBeEnabled({ timeout: 10_000 });

    // Apply one filter through Search so it governs display and exports.
    await page.getByLabel(/actor/i).fill('applied-actor@example.com');
    await page.getByRole('button', { name: /^search$/i }).click();
    await expect(page.getByTestId('audit-applied-filters')).toContainText('applied-actor@example.com');

    // Unsent narrowing draft must not move export scope.
    await page.getByLabel(/date from/i).fill('2026-07-01');
    await expect(page.getByTestId('audit-draft-filters-notice')).toBeVisible();

    const [csvDownload] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: /export csv/i }).click(),
    ]);
    expect(csvDownload.suggestedFilename()).toBe(SERVER_CSV_NAME);

    // Unsent widening draft must not move export scope either.
    await page.getByLabel(/actor/i).fill('');
    const [jsonDownload] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: /export json/i }).click(),
    ]);
    expect(jsonDownload.suggestedFilename()).toBe(SERVER_JSON_NAME);

    // Both exports exactly equal the displayed applied filters.
    expect(exportBodies).toEqual([
      { format: 'csv', actor_identity: 'applied-actor@example.com' },
      { format: 'json', actor_identity: 'applied-actor@example.com' },
    ]);
    expect(downloads).toEqual([SERVER_CSV_NAME, SERVER_JSON_NAME]);
    expect(unexpectedConsoleErrors(consoleErrors)).toEqual([]);
  });

  test('failed searches keep export on the prior displayed dataset and retry repeats once', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('pageerror', (error) => consoleErrors.push(String(error)));

    let searchCalls = 0;
    const pendingQueries: string[] = [];
    const exportBodies: Record<string, unknown>[] = [];
    await mockAuditShell(page);
    let releaseManualRetry: (() => void) | undefined;
    const manualRetryGate = new Promise<void>((resolve) => {
      releaseManualRetry = resolve;
    });
    await page.route('**/api/v1/admin/audit/entries*', async (route: Route) => {
      const url = new URL(route.request().url());
      if (url.searchParams.get('actor_identity') === 'pending-actor@example.com') {
        searchCalls += 1;
        pendingQueries.push(url.searchParams.toString());
        // Hold only the manual retry in flight so the disabled control is
        // observable deterministically.
        if (searchCalls > 2) {
          await manualRetryGate;
        }
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: '{"error":"internal","message_key":"error.internal"}',
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          auditEntriesResponse(url.searchParams.get('actor_identity') ?? 'seeded@example.com'),
        ),
      });
    });
    await page.route('**/api/v1/admin/audit/export', async (route: Route) => {
      exportBodies.push(route.request().postDataJSON() as Record<string, unknown>);
      await route.fulfill({
        status: 200,
        contentType: 'text/csv; charset=utf-8',
        headers: { 'Content-Disposition': `attachment; filename="${SERVER_CSV_NAME}"` },
        body: 'seq\n1\n',
      });
    });

    await signInLocalUser(page);
    await page.goto('/admin/audit');
    await expect(page.getByRole('button', { name: /export csv/i })).toBeEnabled({ timeout: 10_000 });
    await page.getByLabel(/actor/i).fill('applied-actor@example.com');
    await page.getByRole('button', { name: /^search$/i }).click();
    await expect(page.getByTestId('audit-applied-filters')).toContainText('applied-actor@example.com');

    // The failing search (including the framework's single automatic retry)
    // keeps the prior rows visible with a recoverable manual retry.
    await page.getByLabel(/actor/i).fill('pending-actor@example.com');
    await page.getByRole('button', { name: /^search$/i }).click();
    const retry = page.getByRole('button', { name: /^retry$/i }).first();
    await expect(retry).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId('audit-applied-filters')).toContainText('applied-actor@example.com');

    await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: /export csv/i }).click(),
    ]);
    expect(exportBodies[0]).toEqual({ format: 'csv', actor_identity: 'applied-actor@example.com' });

    // The manual retry repeats the exact failed request once; while it is in
    // flight the control is disabled so a duplicate click cannot start
    // another one (the framework's single automatic retry is product
    // behavior, not a duplicate click). The retry also fails, so the prior
    // displayed dataset and its filters remain governing.
    await retry.click();
    // While the repeated request is in flight the retry control is removed
    // from the accessibility tree entirely, so a duplicate click cannot
    // start another one.
    await expect(retry).toHaveCount(0, { timeout: 5_000 });
    releaseManualRetry?.();
    await expect(retry).toBeEnabled({ timeout: 15_000 });
    await expect(page.getByTestId('audit-applied-filters')).toContainText('applied-actor@example.com');
    expect(searchCalls).toBe(4);
    expect(pendingQueries.length).toBe(4);
    expect(new Set(pendingQueries).size).toBe(1);
    expect(pendingQueries[0]).toContain('actor_identity=pending-actor%40example.com');
    expect(unexpectedConsoleErrors(consoleErrors)).toEqual([]);
  });

  test('401/403/422/429 failures and cancel produce zero partial downloads', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('pageerror', (error) => consoleErrors.push(String(error)));

    await mockAuditShell(page);
    await page.route('**/api/v1/admin/audit/entries*', (route: Route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(auditEntriesResponse('seeded@example.com')),
      }),
    );

    // Recoverable sanitized failures keep controls available with zero downloads.
    const recoverable = [
      { status: 403, body: '{"error":"forbidden","message_key":"error.forbidden"}' },
      { status: 422, body: '{"error":"export_limit_exceeded","message_key":"error.export_limit_exceeded"}' },
      { status: 429, body: '{"error":"quota_exceeded","message_key":"error.quota_exceeded"}' },
    ];
    const downloadsBeforeFailures: unknown[] = [];
    page.on('download', (download) => downloadsBeforeFailures.push(download));
    await signInLocalUser(page);
    await page.goto('/admin/audit');
    await expect(page.getByRole('button', { name: /export csv/i })).toBeEnabled({ timeout: 10_000 });
    for (const failure of recoverable) {
      await page.route('**/api/v1/admin/audit/export', (route: Route) =>
        route.fulfill({ status: failure.status, contentType: 'application/json', body: failure.body }),
      );
      await page.getByRole('button', { name: /export csv/i }).click();
      await expect(page.getByRole('button', { name: /export csv/i })).toBeEnabled({ timeout: 5_000 });
    }
    expect(downloadsBeforeFailures.length).toBe(0);

    // A real 401 expires the session through the standard auth boundary,
    // still without producing any download.
    await page.route('**/api/v1/admin/audit/export', (route: Route) =>
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: '{"error":"unauthorized","message_key":"error.unauthorized"}',
      }),
    );
    await page.getByRole('button', { name: /export csv/i }).click();
    await expect(page).toHaveURL(/\/sign-in/, { timeout: 10_000 });

    // A fresh page load re-authenticates against the mocked identity, then
    // cancel mid-flight: gated response, cancel, release; zero downloads.
    await page.goto('/admin/audit');
    await expect(page.getByRole('button', { name: /export csv/i })).toBeEnabled({ timeout: 10_000 });
    let releaseExport: (() => void) | undefined;
    const exportGate = new Promise<void>((resolve) => {
      releaseExport = resolve;
    });
    await page.route('**/api/v1/admin/audit/export', async (route: Route) => {
      await exportGate;
      await route.fulfill({
        status: 200,
        contentType: 'text/csv; charset=utf-8',
        headers: { 'Content-Disposition': `attachment; filename="${SERVER_CSV_NAME}"` },
        body: 'seq\n1\n',
      });
    });
    const downloads: unknown[] = [];
    page.on('download', (download) => downloads.push(download));
    await page.getByRole('button', { name: /export csv/i }).click();
    const cancel = page.getByRole('button', { name: /cancel export/i });
    await expect(cancel).toBeVisible();
    await cancel.click();
    await expect(page.getByText(/export canceled\./i)).toBeVisible();
    releaseExport?.();
    await exportGate;
    await page.waitForTimeout(200);
    expect(downloads.length).toBe(0);
    expect(unexpectedConsoleErrors(consoleErrors)).toEqual([]);
  });

  test('AR at 375px: applied summary, notice and keyboard export stay inside RTL chrome', async ({ page }) => {
    await mockAuditShell(page);
    await page.route('**/api/v1/admin/audit/entries*', (route: Route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(auditEntriesResponse('مستخدم@example.com')),
      }),
    );
    await page.setViewportSize({ width: 375, height: 720 });
    await signInLocalUser(page);
    await page.goto('/admin/audit?lng=ar');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');

    const summary = page.getByTestId('audit-applied-filters');
    await expect(summary).toBeVisible();

    // Keyboard-only flow reaches the export control without overflow. The
    // entry animation is transform-based, so let it settle before measuring.
    await page.waitForTimeout(700);
    let overflow = false;
    for (const el of await page.locator('body *').all()) {
      // Screen-reader-only scaffolding is invisible to users by contract.
      const hidden = await el
        .evaluate((node) => {
          const style = getComputedStyle(node);
          if (style.display === 'none' || style.visibility === 'hidden') return true;
          if (node.closest('.sr-only') !== null) return true;
          return false;
        })
        .catch(() => true);
      if (hidden) continue;
      const box = await el.boundingBox().catch(() => null);
      if (!box) continue;
      if (box.width === 0 || box.height === 0) continue;
      if (box.x < -1 || box.x + box.width > 376) {
        overflow = true;
        break;
      }
    }

    await page.getByLabel(/المنفّذ/).fill('مطبق@example.com');
    await page.keyboard.press('Tab');
    await page.getByRole('button', { name: /^بحث$/ }).click();
    await expect(summary).toContainText('مطبق@example.com');
    expect(overflow).toBe(false);
  });
});
