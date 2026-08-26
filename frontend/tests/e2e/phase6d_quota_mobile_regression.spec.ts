import { expect, test } from '@playwright/test';
import { mockQueryLimits, mockSessionsList } from './helpers/mock-backend';

const quota = {
  role_id: 'mobile-regression-role',
  role_name: 'VeryLongUnbreakableRoleNameForMobileRegressionWithoutBreaks',
  daily_query_limit: 100,
  daily_execution_limit: 50,
  daily_export_limit: 5,
};

test.describe('P6-FR-179 mobile quota actions', () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/auth/me', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'quota-admin-id',
          username: 'quota-admin',
          display_name: 'Quota Administrator',
          role: 'custom',
          permissions: ['admin.quotas.manage'],
        }),
      })
    );
    await page.route('**/api/v1/connections', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ connections: [] }),
      })
    );
    await mockSessionsList(page);
    await mockQueryLimits(page);
    await page.route('**/api/v1/admin/quotas/status', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: [] }),
      })
    );
    await page.route('**/api/v1/admin/quotas', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ quotas: [quota] }),
      })
    );
  });

  for (const locale of ['en', 'ar']) {
    test(`keeps the ${locale} Edit action fully inside the 375px viewport`, async ({
      page,
    }) => {
      await page.goto(`/admin/quotas?lng=${locale}`);

      const edit = page
        .locator('article')
        .getByTitle(locale === 'ar' ? 'تعديل' : 'Edit');
      await expect(edit).toBeVisible();
      const box = await edit.boundingBox();

      expect(box).not.toBeNull();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(375);
    });
  }
});
