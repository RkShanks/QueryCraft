import { expect, test, type Locator, type Page, type Response } from '@playwright/test';
import ar from '../../src/locales/ar.json' with { type: 'json' };
import en from '../../src/locales/en.json' with { type: 'json' };
import type { QueryResult } from '../../src/api/generated/types.gen';
import { signInLocalUser } from './helpers/auth';
import {
  mockConnections,
  mockLocalAuth,
  mockQueryLimits,
  mockSessionsList,
} from './helpers/mock-backend';

const localeMessages: Record<string, Record<string, string>> = { en, ar };
const VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 768, height: 1024 },
  { width: 375, height: 812 },
] as const;
const LOCALES = ['en', 'ar'] as const;
type Locale = (typeof LOCALES)[number];

function message(locale: Locale, key: string): string {
  const value = localeMessages[locale][key];
  if (!value) throw new Error(`Missing locale message for ${key}`);
  return value;
}

/** Every flattened en.json key must never appear as visible text. */
const TRANSLATION_KEYS = Object.keys(en);

interface ObservedRequest {
  method: string;
  path: string;
}

function trackTraffic(page: Page) {
  const requests: ObservedRequest[] = [];
  const serverFailures: string[] = [];
  const pageErrors: string[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/')) {
      requests.push({ method: request.method(), path: url.pathname });
    }
  });
  page.on('response', (response: Response) => {
    if (response.status() >= 500) {
      serverFailures.push(`${response.status()} ${new URL(response.url()).pathname}`);
    }
  });
  return {
    requests,
    serverFailures,
    pageErrors,
    /**
     * Starts collecting uncaught errors and console errors. Armed only after
     * sign-in so the contractual pre-auth 401 bootstrap probe stays out.
     */
    armErrorTracking() {
      page.on('pageerror', (error) => pageErrors.push(String(error)));
      page.on('console', (entry) => {
        if (entry.type() === 'error') pageErrors.push(entry.text());
      });
    },
    expectNoServerFailures(exceptPaths: string[] = []) {
      const unexpected = serverFailures.filter(
        (entry) => !exceptPaths.some((path) => entry.endsWith(path))
      );
      expect(unexpected).toEqual([]);
    },
    /** Asserts how many 5xx responses hit an exempted deliberate-failure path. */
    expectServerFailureCount(path: string, count: number) {
      const matching = serverFailures.filter((entry) => entry.endsWith(path));
      expect(matching).toHaveLength(count);
    },
    expectOnlyRequests(allowed: Array<{ method: string; path: string }>) {
      const allowedKeys = new Set(allowed.map((entry) => `${entry.method} ${entry.path}`));
      const unexpected = requests.filter(
        (entry) => !allowedKeys.has(`${entry.method} ${entry.path}`)
      );
      expect(unexpected).toEqual([]);
    },
    expectNoPageErrors(allowPatterns: RegExp[] = []) {
      const unexpected = pageErrors.filter(
        (entry) => !allowPatterns.some((pattern) => pattern.test(entry))
      );
      expect(unexpected).toEqual([]);
    },
  };
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect
    .poll(() =>
      page.evaluate(() => ({
        root: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        body: document.body.scrollWidth - document.body.clientWidth,
      }))
    )
    .toEqual({ root: 0, body: 0 });
}

async function expectReachableInViewport(page: Page, control: Locator) {
  await control.scrollIntoViewIfNeeded();
  const box = await control.boundingBox();
  expect(box).not.toBeNull();
  if (!box) return;
  const viewport = page.viewportSize() ?? { width: 0, height: 0 };
  expect(box.x).toBeGreaterThanOrEqual(-1);
  expect(box.x + box.width).toBeLessThanOrEqual(viewport.width + 1);
  expect(box.y).toBeGreaterThanOrEqual(-1);
  expect(box.y + box.height).toBeLessThanOrEqual(viewport.height + 1);
}

/**
 * Tabs to the control and asserts a visible focus indicator, following the
 * established XP-008 pattern: keyboard focus must produce a non-none outline
 * or box shadow on the control itself.
 */
async function expectVisibleKeyboardFocus(page: Page, control: Locator) {
  await tabTo(page, control);
  await expect(control).toBeFocused();
  await expect
    .poll(() =>
      control.evaluate((element) => {
        const style = getComputedStyle(element);
        const outlineIsVisible =
          style.outlineStyle !== 'none' && Number.parseFloat(style.outlineWidth) > 0;
        return outlineIsVisible || style.boxShadow !== 'none';
      })
    )
    .toBe(true);
}

async function tabTo(page: Page, target: Locator) {
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  for (let tabs = 0; tabs < 80; tabs += 1) {
    await page.keyboard.press('Tab');
    if (await target.evaluate((element) => element === document.activeElement)) return;
  }
  throw new Error(`Tab navigation did not reach ${await target.getAttribute('data-testid')}`);
}

async function expectNoRawTranslationKeys(page: Page) {
  const visibleText = await page.locator('body').innerText();
  const leaked = TRANSLATION_KEYS.filter((key) => visibleText.includes(key));
  expect(leaked).toEqual([]);
}

async function expectLogicalDirection(page: Page, locale: Locale) {
  await expect(page.locator('html')).toHaveAttribute('lang', locale);
  await expect(page.locator('html')).toHaveAttribute('dir', locale === 'ar' ? 'rtl' : 'ltr');
  const direction = await page
    .locator('body')
    .evaluate((element) => getComputedStyle(element).direction);
  expect(direction).toBe(locale === 'ar' ? 'rtl' : 'ltr');
}

async function installShellMocks(page: Page) {
  await mockLocalAuth(page);
  await mockConnections(page);
  await mockSessionsList(page);
  await mockQueryLimits(page);
}

function resultWithRows(rowCount: number): QueryResult {
  return {
    kind: 'result',
    attempt_id: 'attempt-chunk27',
    question: 'How many actors?',
    generated_sql: 'SELECT count(*) FROM actor;',
    columns: [{ name: 'count', type: 'bigint' }],
    rows: Array.from({ length: rowCount }, (_, index) => [index + 1]),
    row_count: rowCount,
    attempt_number: 1,
    is_last_auto_retry: false,
  };
}

// IS-GAP-046 / CHUNK-27: machine-observable responsive and accessibility evidence.
// Every case asserts geometry, focus, semantics, localized text and request behavior;
// screenshots are never used as proof.
for (const viewport of VIEWPORTS) {
  for (const locale of LOCALES) {
    test(`[${viewport.width}px ${locale}] workspace renders bounded results with reachable controls`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      const traffic = trackTraffic(page);
      await installShellMocks(page);

      let submitCalls = 0;
      await page.route('**/api/v1/query/submit', async (route) => {
        submitCalls += 1;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(resultWithRows(80)),
        });
      });

      await signInLocalUser(page);
      traffic.armErrorTracking();
      await page.goto(`/?lng=${locale}`);

      await expectLogicalDirection(page, locale);
      await expect(page.getByTestId('workspace-page')).toBeVisible();
      await expect(page.getByText(message(locale, 'workspace.emptyState'))).toBeVisible();

      // Sidebar and workspace stay separated in both logical directions.
      const sidebar = await page.getByTestId('app-shell-sidebar').boundingBox();
      const workspace = await page.getByTestId('app-shell-workspace').boundingBox();
      expect(sidebar).not.toBeNull();
      expect(workspace).not.toBeNull();
      if (sidebar && workspace) {
        const separated =
          sidebar.x + sidebar.width <= workspace.x + 1 ||
          workspace.x + workspace.width <= sidebar.x + 1;
        expect(separated).toBe(true);
      }

      const prompt = page.getByLabel(message(locale, 'query.input.label'));
      await expectReachableInViewport(page, prompt);
      const promptWrapper = page.locator('.prompt-input-wrapper');
      const unfocusedWrapper = await promptWrapper.evaluate((element) => {
        const style = getComputedStyle(element);
        return { borderColor: style.borderColor, boxShadow: style.boxShadow };
      });
      await tabTo(page, prompt);
      await expect(prompt).toBeFocused();
      await expect
        .poll(() =>
          promptWrapper.evaluate((element) => {
            const style = getComputedStyle(element);
            return { borderColor: style.borderColor, boxShadow: style.boxShadow };
          })
        )
        .not.toEqual(unfocusedWrapper);

      await expectNoHorizontalOverflow(page);
      await expectNoRawTranslationKeys(page);
      traffic.expectNoServerFailures();

      const askButton = page.getByRole('button', { name: message(locale, 'common.send') });
      await prompt.fill('How many actors?');
      await askButton.click();
      const resultTable = page.getByTestId('result-table');
      await expect(resultTable).toBeVisible();

      // Result rendering stays bounded: exactly one 50-row DOM page plus pagination.
      await expect(resultTable.locator('tbody tr')).toHaveCount(50);
      const pagination = resultTable.getByRole('navigation', {
        name: message(locale, 'query.result.pagination.label'),
      });
      await expectReachableInViewport(page, pagination);
      await pagination
        .getByRole('button', { name: message(locale, 'query.result.pagination.next') })
        .click();
      await expect(resultTable.locator('tbody tr')).toHaveCount(30);
      await pagination
        .getByRole('button', { name: message(locale, 'query.result.pagination.previous') })
        .click();
      await expect(resultTable.locator('tbody tr')).toHaveCount(50);

      expect(submitCalls).toBe(1);
      traffic.expectNoServerFailures();
      traffic.expectOnlyRequests([
        { method: 'GET', path: '/api/v1/auth/me' },
        { method: 'POST', path: '/api/v1/auth/sign-in' },
        { method: 'GET', path: '/api/v1/auth/sso/providers' },
        { method: 'GET', path: '/api/v1/connections' },
        { method: 'GET', path: '/api/v1/query/limits' },
        { method: 'GET', path: '/api/v1/sessions' },
        { method: 'POST', path: '/api/v1/query/submit' },
      ]);
      traffic.expectNoPageErrors();
    });

    test(`[${viewport.width}px ${locale}] rejection, failure alerts and retry transition stay observable`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      const traffic = trackTraffic(page);
      await installShellMocks(page);

      let submitCalls = 0;
      await page.route('**/api/v1/query/submit', async (route) => {
        submitCalls += 1;
        if (submitCalls === 1) {
          const rejection = { message_key: 'query.evaluator.rejected', violations: [] };
          await route.fulfill({
            status: 422,
            contentType: 'application/json',
            body: JSON.stringify(rejection),
          });
          return;
        }
        if (submitCalls === 2) {
          const failure = { error: 'llm_unavailable', message_key: 'error.llmUnavailable' };
          await route.fulfill({
            status: 502,
            contentType: 'application/json',
            body: JSON.stringify(failure),
          });
          return;
        }
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(resultWithRows(1)),
        });
      });

      await signInLocalUser(page);
      traffic.armErrorTracking();
      await page.goto(`/?lng=${locale}`);
      const prompt = page.getByLabel(message(locale, 'query.input.label'));
      const askButton = page.getByRole('button', { name: message(locale, 'common.send') });

      // Dynamic validation state: empty questions never reach the API.
      await expect(prompt).toBeEnabled();
      await expect(askButton).toBeDisabled();
      expect(submitCalls).toBe(0);

      await prompt.fill('How many actors?');
      await expect(askButton).toBeEnabled();
      await askButton.click();
      await expect(page.getByTestId('rejection-banner')).toContainText(
        message(locale, 'query.evaluatorRejection.heading')
      );
      await expectReachableInViewport(page, page.getByTestId('rejection-banner'));

      await prompt.fill('How many actors again?');
      await askButton.click();
      const alert = page
        .getByRole('alert')
        .filter({ hasText: message(locale, 'error.llmUnavailable') });
      await expect(alert).toBeVisible();

      await prompt.fill('How many actors finally?');
      await askButton.click();
      await expect(page.getByTestId('result-table')).toBeVisible();
      expect(submitCalls).toBe(3);

      await expectNoHorizontalOverflow(page);
      await expectNoRawTranslationKeys(page);
      // The llmUnavailable simulation is the only deliberate 5xx on this path.
      traffic.expectServerFailureCount('/api/v1/query/submit', 1);
      traffic.expectNoServerFailures(['/api/v1/query/submit']);
      traffic.expectOnlyRequests([
        { method: 'GET', path: '/api/v1/auth/me' },
        { method: 'POST', path: '/api/v1/auth/sign-in' },
        { method: 'GET', path: '/api/v1/auth/sso/providers' },
        { method: 'GET', path: '/api/v1/connections' },
        { method: 'GET', path: '/api/v1/query/limits' },
        { method: 'GET', path: '/api/v1/sessions' },
        { method: 'POST', path: '/api/v1/query/submit' },
      ]);
      // Chromium logs resource entries for the deliberate 422/502 mocks.
      traffic.expectNoPageErrors([/status of 422/, /status of 502/]);
    });

    test(`[${viewport.width}px ${locale}] history list supports search, bounded paging and selection`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      const traffic = trackTraffic(page);
      await installShellMocks(page);

      const historyItemA = {
        id: 'history-a',
        question_text: 'Count actors',
        generated_sql: 'SELECT count(*) FROM actor;',
        accepted_at: '2026-08-20T09:00:00Z',
      };
      const historyItemB = {
        id: 'history-b',
        question_text: 'Count customers',
        generated_sql: 'SELECT count(*) FROM customer;',
        accepted_at: '2026-08-21T09:00:00Z',
      };

      let listCalls = 0;
      // Registered first: the detail handler below falls back to this one.
      await page.route(/\/api\/v1\/history(?:\?.*)?$/, async (route) => {
        listCalls += 1;
        const url = new URL(route.request().url());
        const search = url.searchParams.get('search') ?? '';
        if (search.trim()) {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ items: [], total: 0, next_cursor: null }),
          });
          return;
        }
        const cursor = url.searchParams.get('cursor');
        const payload =
          cursor === 'cursor-2'
            ? { items: [historyItemB], total: 2, next_cursor: null }
            : { items: [historyItemA], total: 2, next_cursor: 'cursor-2' };
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(payload),
        });
      });
      await page.route('**/api/v1/history/*', async (route) => {
        const url = new URL(route.request().url());
        if (!/\/history\/[^/]+$/.test(url.pathname)) {
          await route.fallback();
          return;
        }
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...historyItemA,
            llm_provider: 'gemini',
            database_connection_name: 'Local Pagila',
            database_type: 'postgresql',
          }),
        });
      });

      await signInLocalUser(page);
      traffic.armErrorTracking();
      await page.goto(`/history?lng=${locale}`);

      await expectLogicalDirection(page, locale);
      const firstRow = page.getByTestId('history-row').first();
      await expect(firstRow).toBeVisible();
      await expectReachableInViewport(page, firstRow);

      // Explicit bounded paging: Load more issues one cursor-bound request.
      const loadMore = page.getByRole('button', { name: message(locale, 'history.loadMore') });
      await expect(loadMore).toBeVisible();
      await loadMore.click();
      await expect(page.getByText('Count customers')).toBeVisible();
      expect(listCalls).toBe(2);

      // Selection semantics are exposed on accessible buttons.
      const detailPanel = page.getByTestId('history-detail-panel');
      await firstRow.click();
      await expect(firstRow).toHaveAttribute('aria-pressed', 'true');
      await expect(detailPanel).toContainText(message(locale, 'history.detail.question'));

      // Server-side search drives a no-match empty state without overflow.
      await page.getByLabel(message(locale, 'history.filter.placeholder')).fill('zzz-no-match-zzz');
      await expect(page.getByText(message(locale, 'history.noMatch'))).toBeVisible({
        timeout: 5_000,
      });

      await expectNoHorizontalOverflow(page);
      await expectNoRawTranslationKeys(page);
      traffic.expectNoServerFailures();
      traffic.expectOnlyRequests([
        { method: 'GET', path: '/api/v1/auth/me' },
        { method: 'POST', path: '/api/v1/auth/sign-in' },
        { method: 'GET', path: '/api/v1/auth/sso/providers' },
        { method: 'GET', path: '/api/v1/connections' },
        { method: 'GET', path: '/api/v1/query/limits' },
        { method: 'GET', path: '/api/v1/sessions' },
        { method: 'GET', path: '/api/v1/history' },
        { method: 'GET', path: '/api/v1/history/history-a' },
      ]);
      traffic.expectNoPageErrors();
    });

    test(`[${viewport.width}px ${locale}] roles table scrolls boundedly and denial blocks data access`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      const traffic = trackTraffic(page);
      await installShellMocks(page);

      const customRole = {
        id: 'role-chunk27-custom',
        name: 'Responsive Evidence Analysts With Extended Review Duties',
        description: 'Reviews policy enforcement.',
        priority: 20,
        permissions: ['query.submit'],
        is_builtin: false,
        group_mappings: [],
        connection_policy_count: 0,
        connection_policies: [],
        created_at: '2026-08-24T00:00:00Z',
        updated_at: '2026-08-24T00:00:00Z',
      };

      await page.route('**/api/v1/admin/sso/group-mappings', async (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ mappings: [] }),
        })
      );
      await page.route('**/api/v1/admin/roles**', async (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ roles: [customRole] }),
        })
      );

      await signInLocalUser(page);
      traffic.armErrorTracking();
      await page.goto(`/admin/roles?lng=${locale}`);

      await expectLogicalDirection(page, locale);
      const rolesRegion = page.getByTestId('roles-table-scroll');
      await expect(rolesRegion).toBeVisible();

      // The table region owns horizontal overflow so the page never does.
      await expect
        .poll(() =>
          rolesRegion.evaluate((element) => getComputedStyle(element).overflowX)
        )
        .toBe('auto');
      if (viewport.width <= 768) {
        await expect
          .poll(() =>
            rolesRegion.evaluate(
              (element) => element.scrollWidth > element.clientWidth
            )
          )
          .toBe(true);
      }
      await expectNoHorizontalOverflow(page);

      const editAction = page.getByTestId(`edit-role-${customRole.id}`);
      await expect(editAction).toBeAttached();
      await editAction.scrollIntoViewIfNeeded();
      const actionBox = await editAction.boundingBox();
      const regionBox = await rolesRegion.boundingBox();
      expect(actionBox).not.toBeNull();
      expect(regionBox).not.toBeNull();
      if (actionBox && regionBox) {
        expect(actionBox.x).toBeGreaterThanOrEqual(regionBox.x - 1);
        expect(actionBox.x + actionBox.width).toBeLessThanOrEqual(regionBox.x + regionBox.width + 1);
      }
      await expectVisibleKeyboardFocus(page, editAction);

      await expectNoRawTranslationKeys(page);
      traffic.expectNoServerFailures();

      // Permission denial: without admin.roles.manage the route denies access
      // and never issues another roles request. A later-registered handler
      // takes precedence for the reload.
      const rolesCallsBefore = traffic.requests.filter((entry) =>
        entry.path.startsWith('/api/v1/admin/roles')
      ).length;
      await page.route('**/api/v1/auth/me', async (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'restricted-user',
            username: 'restricted_user',
            display_name: 'Restricted User',
            role: 'custom',
            permissions: ['query.submit'],
          }),
        })
      );
      await page.goto(`/admin/roles?lng=${locale}`);
      await expect(
        page.getByRole('heading', { name: message(locale, 'accessDenied.title') })
      ).toBeVisible();
      const rolesCallsAfter = traffic.requests.filter((entry) =>
        entry.path.startsWith('/api/v1/admin/roles')
      ).length;
      expect(rolesCallsAfter).toBe(rolesCallsBefore);
      await expectNoHorizontalOverflow(page);
      traffic.expectOnlyRequests([
        { method: 'GET', path: '/api/v1/auth/me' },
        { method: 'POST', path: '/api/v1/auth/sign-in' },
        { method: 'GET', path: '/api/v1/auth/sso/providers' },
        { method: 'GET', path: '/api/v1/connections' },
        { method: 'GET', path: '/api/v1/query/limits' },
        { method: 'GET', path: '/api/v1/sessions' },
        { method: 'GET', path: '/api/v1/admin/sso/group-mappings' },
        { method: 'GET', path: '/api/v1/admin/roles' },
      ]);
      traffic.expectNoPageErrors();
    });

    test(`[${viewport.width}px ${locale}] connection delete dialog traps focus across viewports`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      const traffic = trackTraffic(page);
      await installShellMocks(page);
      await page.route('**/api/v1/admin/connections', async (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            {
              id: '550e8400-e29b-41d4-a716-4466554400c7',
              display_name: 'Analytics warehouse',
              database_type: 'postgresql',
              database_name: 'analytics',
              port: 5432,
              ssl_mode: 'require',
              lifecycle_state: 'active',
              health_status: 'healthy',
              health_error_category: null,
              last_health_check_at: '2026-08-24T10:00:00Z',
              schema_introspection_status: 'success',
              schema_last_refreshed_at: '2026-08-24T10:00:00Z',
              created_at: '2026-08-24T09:00:00Z',
              updated_at: '2026-08-24T10:00:00Z',
            },
          ]),
        })
      );

      await signInLocalUser(page);
      traffic.armErrorTracking();
      await page.goto(`/admin/connections?lng=${locale}`);

      const deleteButton = page
        .getByRole('button', { name: message(locale, 'common.delete') })
        .first();
      await expectReachableInViewport(page, deleteButton);
      await deleteButton.click();

      const dialog = page.getByRole('dialog');
      await expect(dialog).toBeVisible();
      await expect(dialog).toHaveAttribute('aria-modal', 'true');

      // Focus starts on the least destructive control and cycles inside.
      const cancelButton = dialog.getByRole('button', { name: message(locale, 'common.cancel') });
      await expect(cancelButton).toBeFocused();
      for (let tabs = 0; tabs < 8; tabs += 1) {
        await page.keyboard.press('Tab');
        const insideDialog = await page.evaluate(
          () =>
            document.activeElement instanceof HTMLElement &&
            !!document.activeElement.closest('[role="dialog"]')
        );
        expect(insideDialog).toBe(true);
      }

      // Escape cancels and restores focus to the trigger.
      await page.keyboard.press('Escape');
      await expect(dialog).toHaveCount(0);
      await expect(deleteButton).toBeFocused();

      await expectNoHorizontalOverflow(page);
      await expectNoRawTranslationKeys(page);
      traffic.expectNoServerFailures();
      traffic.expectNoPageErrors();
    });

    test(`[${viewport.width}px ${locale}] audit export controls initiate contract-compliant downloads`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      const traffic = trackTraffic(page);
      await installShellMocks(page);

      await page.route('**/api/v1/admin/audit/status', async (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ total_entries: 1, last_verification: null }),
        })
      );
      await page.route('**/api/v1/admin/audit/retention', async (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            retention_months: 24,
            last_purge_at: null,
            purged_count: null,
          }),
        })
      );
      await page.route('**/api/v1/admin/audit/entries**', async (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            entries: [
              {
                sequence_number: 1,
                timestamp: '2026-08-24T10:00:00Z',
                actor_identity: 'audit.actor',
                action_type: 'query.submit',
                resource_type: 'database',
                resource_id: 'resource-1',
                outcome: 'success',
                context: {},
              },
            ],
            pagination: { page: 1, page_size: 10, total_entries: 1, total_pages: 1 },
          }),
        })
      );

      let exportCalls = 0;
      let exportMethod = '';
      await page.route('**/api/v1/admin/audit/export', async (route) => {
        exportCalls += 1;
        exportMethod = route.request().method();
        await route.fulfill({
          status: 200,
          contentType: 'text/csv',
          headers: { 'content-disposition': 'attachment; filename="audit_export.csv"' },
          body: 'sequence_number\n1\n',
        });
      });

      await signInLocalUser(page);
      traffic.armErrorTracking();
      await page.goto(`/admin/audit?lng=${locale}`);

      await expectLogicalDirection(page, locale);
      await expect(page.getByText('audit.actor')).toBeVisible();

      const csvButton = page.getByRole('button', { name: message(locale, 'audit.export.csv') });
      await expect(csvButton).toBeEnabled();
      await expectReachableInViewport(page, csvButton);
      await expectVisibleKeyboardFocus(page, csvButton);
      await page.keyboard.press('Enter');

      await expect.poll(() => exportCalls).toBe(1);
      expect(exportMethod).toBe('POST');

      await expectNoHorizontalOverflow(page);
      await expectNoRawTranslationKeys(page);
      traffic.expectNoServerFailures();
      traffic.expectOnlyRequests([
        { method: 'GET', path: '/api/v1/auth/me' },
        { method: 'POST', path: '/api/v1/auth/sign-in' },
        { method: 'GET', path: '/api/v1/auth/sso/providers' },
        { method: 'GET', path: '/api/v1/connections' },
        { method: 'GET', path: '/api/v1/query/limits' },
        { method: 'GET', path: '/api/v1/sessions' },
        { method: 'GET', path: '/api/v1/admin/audit/status' },
        { method: 'GET', path: '/api/v1/admin/audit/retention' },
        { method: 'GET', path: '/api/v1/admin/audit/entries' },
        { method: 'POST', path: '/api/v1/admin/audit/export' },
      ]);
      traffic.expectNoPageErrors();
    });
  }
}
