import { expect, test, type Locator, type Page } from '@playwright/test';
import { mockConnections, mockLocalAuth } from './helpers/mock-backend';
import { signInLocalUser } from './helpers/auth';

const customRole = {
  id: 'mobile-custom-role',
  name: 'Security Analysts With Extended Access Review Duties',
  description: 'Reviews policy enforcement across all protected source databases.',
  priority: 20,
  permissions: [
    'query.submit',
    'query.history.view',
    'admin.connections.manage',
    'admin.roles.manage',
  ],
  is_builtin: false,
  group_mappings: [
    {
      id: 'mobile-custom-mapping',
      sso_group_value: 'identity-provider-security-analysts',
    },
  ],
  connection_policy_count: 1,
  connection_policies: [],
  created_at: '2026-07-30T00:00:00Z',
  updated_at: '2026-07-30T00:00:00Z',
};

const builtinRole = {
  ...customRole,
  id: 'mobile-builtin-role',
  name: 'Admin',
  priority: 0,
  is_builtin: true,
  group_mappings: [],
};

async function mockRoleAdminData(page: Page) {
  await mockLocalAuth(page);
  await mockConnections(page);
  await page.route('**/api/v1/sessions', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ sessions: [] }),
    })
  );
  await page.route('**/api/v1/admin/roles**', async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;

    if (request.method() === 'DELETE' && pathname.endsWith(`/${customRole.id}`)) {
      await route.fulfill({ status: 204 });
      return;
    }
    if (request.method() === 'GET' && pathname.endsWith(`/${customRole.id}`)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(customRole),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ roles: [customRole, builtinRole] }),
    });
  });
}

async function focusWithTab(page: Page, target: Locator) {
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  });

  for (let tabCount = 0; tabCount < 80; tabCount += 1) {
    await page.keyboard.press('Tab');
    if (await target.evaluate((element) => element === document.activeElement)) {
      return;
    }
  }

  throw new Error(`Tab navigation did not reach ${await target.getAttribute('data-testid')}`);
}

async function expectInsideScrollRegion(page: Page, action: Locator, region: Locator) {
  const [actionBox, regionBox] = await Promise.all([
    action.boundingBox(),
    region.boundingBox(),
  ]);

  expect(actionBox).not.toBeNull();
  expect(regionBox).not.toBeNull();
  expect(actionBox!.x).toBeGreaterThanOrEqual(Math.max(0, regionBox!.x));
  expect(actionBox!.x + actionBox!.width).toBeLessThanOrEqual(
    Math.min(await page.evaluate(() => document.documentElement.clientWidth), regionBox!.x + regionBox!.width)
  );
}

async function expectVisibleKeyboardFocus(action: Locator) {
  const hasVisibleFocus = await action.evaluate((element) => {
    const style = window.getComputedStyle(element);
    const outlineIsVisible =
      style.outlineStyle !== 'none' && Number.parseFloat(style.outlineWidth) > 0;
    return outlineIsVisible || style.boxShadow !== 'none';
  });

  expect(hasVisibleFocus).toBe(true);
}

for (const viewport of [
  { width: 375, height: 812 },
  { width: 768, height: 1024 },
]) {
  for (const locale of ['en', 'ar']) {
    test(`keeps ${locale} role actions reachable at ${viewport.width}px`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await mockRoleAdminData(page);
      await signInLocalUser(page);
      await page.goto(`/admin/roles?lng=${locale}`);

      await expect(page.locator('html')).toHaveAttribute(
        'dir',
        locale === 'ar' ? 'rtl' : 'ltr'
      );
      const rolesRegion = page.getByTestId('roles-table-scroll');
      const editAction = page.getByTestId(`edit-role-${customRole.id}`);
      const deleteAction = page.getByTestId(`delete-role-${customRole.id}`);

      await expect(rolesRegion).toBeVisible();
      await expect
        .poll(() =>
          page.evaluate(
            () => document.documentElement.scrollWidth - document.documentElement.clientWidth
          )
        )
        .toBeLessThanOrEqual(0);
      await expect
        .poll(() =>
          rolesRegion.evaluate((element) => {
            const style = window.getComputedStyle(element);
            return {
              overflowX: style.overflowX,
              hasOverflow: element.scrollWidth > element.clientWidth,
            };
          })
        )
        .toEqual({ overflowX: 'auto', hasOverflow: true });

      await focusWithTab(page, editAction);
      await expectInsideScrollRegion(page, editAction, rolesRegion);
      await expectVisibleKeyboardFocus(editAction);
      await page.keyboard.press('Enter');
      await expect(
        page.getByRole('heading', {
          name:
            locale === 'ar'
              ? 'تعديل الدور'
              : 'Edit Role',
        })
      ).toBeVisible();

      const cancelAction = page.getByRole('button', {
        name: locale === 'ar' ? 'إلغاء' : 'Cancel',
      });
      await cancelAction.focus();
      await page.keyboard.press('Enter');

      await focusWithTab(page, deleteAction);
      await expectInsideScrollRegion(page, deleteAction, rolesRegion);
      await expectVisibleKeyboardFocus(deleteAction);
      page.once('dialog', (dialog) => dialog.accept());
      const deleteRequest = page.waitForRequest(
        (request) =>
          request.method() === 'DELETE' &&
          new URL(request.url()).pathname.endsWith(`/${customRole.id}`)
      );
      await page.keyboard.press('Enter');
      await deleteRequest;

      await expect(page.getByTestId(`delete-role-${builtinRole.id}`)).toHaveCount(0);
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
