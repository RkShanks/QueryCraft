import { expect, test, type Page, type Route } from '@playwright/test';

import type {
  AuditRetentionResponse,
  AuditSearchResponse,
  AuditStatusResponse,
  ConnectionResponse,
  UserProfile,
} from '../../src/api/generated/types.gen';

const CANARY = 'MALFORMED_SECRET_CANARY';
const ADMIN_ID = '550e8400-e29b-41d4-a716-446655440041';
const CONNECTION_ID = '550e8400-e29b-41d4-a716-446655440042';

function profile(permission: string): UserProfile {
  return {
    id: ADMIN_ID,
    username: 'contract-admin',
    display_name: 'Contract Admin',
    role: 'admin',
    permissions: [permission],
  };
}

async function installIdentity(page: Page, permission: string) {
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(profile(permission)),
    })
  );
}

function validConnection(): ConnectionResponse {
  return {
    id: CONNECTION_ID,
    display_name: 'Production database',
    database_type: 'postgresql',
    database_name: 'analytics',
    port: 5432,
    ssl_mode: 'require',
    lifecycle_state: 'active',
    health_status: 'healthy',
    health_error_category: null,
    last_health_check_at: '2026-08-14T10:00:00Z',
    schema_introspection_status: 'success',
    schema_last_refreshed_at: '2026-08-14T10:00:00Z',
    created_at: '2026-08-14T09:00:00Z',
    updated_at: '2026-08-14T10:00:00Z',
  };
}

async function assertCanaryAbsent(page: Page, consoleMessages: string[]) {
  const bodyText = (await page.locator('body').innerText()) ?? '';
  const accessibilityText = await page.locator('body').ariaSnapshot();
  const storageText = await page.evaluate(() =>
    JSON.stringify({
      local: Object.values(localStorage),
      session: Object.values(sessionStorage),
    })
  );

  expect(bodyText).not.toContain(CANARY);
  expect(accessibilityText).not.toContain(CANARY);
  expect(storageText).not.toContain(CANARY);
  expect(consoleMessages.join('\n')).not.toContain(CANARY);
}

for (const locale of [
  {
    language: 'en',
    invalid: 'The server returned an invalid response. Please try again.',
    retry: 'Retry',
  },
  {
    language: 'ar',
    invalid: 'أعاد الخادم استجابة غير صالحة. يُرجى المحاولة مرة أخرى.',
    retry: 'إعادة المحاولة',
  },
]) {
  test(`malformed initial response is isolated and explicitly retried in ${locale.language}`, async ({
    page,
  }, testInfo) => {
    const consoleMessages: string[] = [];
    page.on('console', (message) => consoleMessages.push(message.text()));
    await installIdentity(page, 'admin.connections.manage');

    let requestCount = 0;
    await page.route('**/api/v1/admin/connections', async (route: Route) => {
      requestCount += 1;
      if (requestCount === 1) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([{ id: 17, nested: { secret: CANARY } }]),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([validConnection()]),
      });
    });

    await page.goto(`/admin/connections?lng=${locale.language}`);
    const alert = page.getByRole('alert', { name: locale.invalid });
    await expect(alert).toBeVisible();
    expect(requestCount).toBe(1);
    await assertCanaryAbsent(page, consoleMessages);
    await page.screenshot({
      path: testInfo.outputPath(`malformed-initial-${locale.language}.png`),
      fullPage: true,
    });

    await alert.getByRole('button', { name: locale.retry }).click();
    await expect(page.getByText('Production database')).toBeVisible();
    expect(requestCount).toBe(2);
    await assertCanaryAbsent(page, consoleMessages);
  });
}

test('preserves valid audit data across partial, refresh, malformed, empty, and late states', async ({
  page,
}, testInfo) => {
  await installIdentity(page, 'admin.audit.verify');

  const status = {
    total_entries: 2,
    last_verification: null,
  } satisfies AuditStatusResponse;
  const retention = {
    retention_months: 24,
    last_purge_at: null,
    purged_count: null,
  } satisfies AuditRetentionResponse;
  await page.route('**/api/v1/admin/audit/status', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(status) })
  );
  await page.route('**/api/v1/admin/audit/retention', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(retention) })
  );

  const auditResponse = (actor: string, partial = false): AuditSearchResponse => ({
    entries: [
      {
        sequence_number: actor === 'new.actor' ? 3 : 1,
        timestamp: '2026-08-14T10:00:00Z',
        actor_identity: actor,
        action_type: 'query.submit',
        resource_type: 'database',
        resource_id: CONNECTION_ID,
        outcome: 'success',
        context: {},
      },
    ],
    pagination: {
      page: 1,
      page_size: 1,
      total_entries: partial ? 2 : 1,
      total_pages: partial ? 2 : 1,
    },
  });

  let releaseMalformed!: () => void;
  const malformedGate = new Promise<void>((resolve) => {
    releaseMalformed = resolve;
  });
  let releaseOld!: () => void;
  let oldRequestStarted!: () => void;
  const oldStarted = new Promise<void>((resolve) => {
    oldRequestStarted = resolve;
  });
  const oldGate = new Promise<void>((resolve) => {
    releaseOld = resolve;
  });

  await page.route('**/api/v1/admin/audit/entries**', async (route) => {
    const action = new URL(route.request().url()).searchParams.get('action_type');
    if (action === 'malformed') {
      await malformedGate;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          entries: [{ timestamp: 'invalid', nested: [CANARY] }],
          pagination: { page: 0, page_size: -1, total_entries: -1, total_pages: -1 },
        }),
      });
      return;
    }
    if (action === 'empty') {
      const empty = {
        entries: [],
        pagination: { page: 1, page_size: 10, total_entries: 0, total_pages: 0 },
      } satisfies AuditSearchResponse;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(empty) });
      return;
    }
    if (action === 'old') {
      oldRequestStarted();
      await oldGate;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(auditResponse('old.actor')) });
      return;
    }
    if (action === 'new') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(auditResponse('new.actor')) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(auditResponse('baseline.actor', true)) });
  });

  await page.goto('/admin/audit?lng=en');
  await expect(page.getByText('baseline.actor')).toBeVisible();
  await expect(page.getByRole('status')).toContainText('More results are available.');

  await page.getByLabel('Action Type').fill('malformed');
  await page.getByRole('button', { name: 'Search' }).click();
  await expect(page.getByRole('status')).toContainText('Refreshing data…');
  releaseMalformed();
  await expect(page.getByRole('alert')).toContainText(
    'The latest refresh was invalid. Showing the last valid data.'
  );
  await expect(page.getByText('baseline.actor')).toBeVisible();
  await assertCanaryAbsent(page, []);
  await page.screenshot({ path: testInfo.outputPath('malformed-background.png'), fullPage: true });

  await page.getByLabel('Action Type').fill('empty');
  await page.getByRole('button', { name: 'Search' }).click();
  await expect(page.getByText('No audit entries found.')).toBeVisible();
  await expect(page.getByRole('status')).toHaveCount(0);

  await page.getByLabel('Action Type').fill('old');
  await page.getByRole('button', { name: 'Search' }).click();
  await oldStarted;
  await page.getByLabel('Action Type').fill('new');
  await page.getByRole('button', { name: 'Search' }).click();
  await expect(page.getByText('new.actor')).toBeVisible();
  releaseOld();
  await page.waitForTimeout(100);
  await expect(page.getByText('new.actor')).toBeVisible();
  await expect(page.getByText('old.actor')).toHaveCount(0);
});
