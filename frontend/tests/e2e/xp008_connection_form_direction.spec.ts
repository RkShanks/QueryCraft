import { expect, test, type Locator, type Page } from '@playwright/test';
import en from '../../src/locales/en.json' with { type: 'json' };
import ar from '../../src/locales/ar.json' with { type: 'json' };
import { mockConnections, mockLocalAuth } from './helpers/mock-backend';
import { signInLocalUser } from './helpers/auth';

const connection = {
  id: 'direction-check',
  display_name: 'قاعدة التحليلات',
  database_type: 'postgresql',
  port: 5432,
  database_name: 'analytics_db',
  ssl_mode: 'require',
  lifecycle_state: 'active',
  health_status: 'healthy',
  last_health_check_at: null,
  health_error_category: null,
  schema_introspection_status: 'success',
  schema_last_refreshed_at: null,
  created_at: '2026-07-30T00:00:00Z',
  updated_at: '2026-07-30T00:00:00Z',
};

const localeMessages = { en, ar } as const;
const technicalKeys = [
  'admin.connections.form.databaseType',
  'admin.connections.form.host',
  'admin.connections.form.port',
  'admin.connections.form.databaseName',
  'admin.connections.form.username',
  'admin.connections.form.password',
  'admin.connections.form.sslMode',
] as const;

function message(locale: 'en' | 'ar', key: string) {
  return (localeMessages[locale] as Record<string, string>)[key];
}

async function mockAdminConnections(page: Page, updateShape: { writeOnlyKeysAbsent: boolean }) {
  await mockLocalAuth(page);
  await mockConnections(page);
  await page.route('**/api/v1/sessions', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ sessions: [] }),
    })
  );
  await page.route('**/api/v1/admin/connections**', async (route) => {
    if (route.request().method() === 'PUT') {
      const payload = route.request().postDataJSON() as Record<string, unknown>;
      updateShape.writeOnlyKeysAbsent = ['host', 'username', 'password'].every(
        (key) => !Object.hasOwn(payload, key)
      );
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(connection),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ connections: [connection] }),
    });
  });
}

async function focusWithTab(page: Page, target: Locator) {
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  for (let tabCount = 0; tabCount < 80; tabCount += 1) {
    await page.keyboard.press('Tab');
    if (await target.evaluate((element) => element === document.activeElement)) return;
  }
  throw new Error(`Tab navigation did not reach ${await target.getAttribute('id')}`);
}

async function expectDirection(control: Locator, direction: 'ltr' | 'rtl') {
  await expect.poll(() => control.evaluate((element) => getComputedStyle(element).direction))
    .toBe(direction);
}

for (const viewport of [
  { width: 375, height: 812 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
]) {
  for (const locale of ['en', 'ar'] as const) {
    test(`isolates ${locale} connection values at ${viewport.width}px`, async ({ page }) => {
      const updateShape = { writeOnlyKeysAbsent: false };
      await page.setViewportSize(viewport);
      await mockAdminConnections(page, updateShape);
      await signInLocalUser(page);
      await page.goto(`/admin/connections?lng=${locale}`);

      const rootDirection = locale === 'ar' ? 'rtl' : 'ltr';
      await expect(page.locator('html')).toHaveAttribute('dir', rootDirection);
      await page.getByRole('button', { name: message(locale, 'admin.connections.add') }).click();

      const form = page.locator('form');
      await expectDirection(form, rootDirection);
      await expectDirection(
        form.getByLabel(message(locale, 'admin.connections.form.displayName')),
        rootDirection
      );
      for (const key of technicalKeys) {
        await expectDirection(form.getByLabel(message(locale, key)), 'ltr');
      }

      const databaseType = form.getByLabel(
        message(locale, 'admin.connections.form.databaseType')
      );
      await focusWithTab(page, databaseType);
      await expect
        .poll(() => databaseType.evaluate((element) => getComputedStyle(element).boxShadow))
        .not.toBe('none');
      await page.getByRole('button', { name: message(locale, 'common.cancel') }).click();

      const edit = page.getByRole('button', { name: message(locale, 'common.edit') });
      await edit.scrollIntoViewIfNeeded();
      await edit.press('Enter');
      for (const key of technicalKeys) {
        await expectDirection(form.getByLabel(message(locale, key)), 'ltr');
      }
      for (const key of [
        'admin.connections.form.host',
        'admin.connections.form.username',
        'admin.connections.form.password',
      ]) {
        await expect(form.getByLabel(message(locale, key))).toHaveValue('');
      }

      const updateRequest = page.waitForRequest(
        (request) =>
          request.method() === 'PUT' &&
          new URL(request.url()).pathname.endsWith(`/${connection.id}`)
      );
      await page
        .getByRole('button', { name: message(locale, 'admin.connections.form.submit.edit') })
        .press('Enter');
      await updateRequest;
      expect(updateShape.writeOnlyKeysAbsent).toBe(true);
      await expect
        .poll(() =>
          page.evaluate(
            () => document.documentElement.scrollWidth - document.documentElement.clientWidth
          )
        )
        .toBeLessThanOrEqual(0);
    });
  }
}
