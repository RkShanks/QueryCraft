import { expect, test, type Locator, type Page } from '@playwright/test';

const roleId = 'chunk-09-role';
const pendingResponse = {
  error: 'quota_sync_pending',
  message_key: 'error.quota_sync_pending',
  mutation_applied: true,
};

interface QuotaConfig {
  role_id: string;
  role_name: string;
  daily_query_limit: number | null;
  daily_execution_limit: number | null;
  daily_export_limit: number | null;
}

interface QuotaBackendState {
  quota: QuotaConfig | null;
  listRequests: number;
  mutationBodies: unknown[];
  mutationRequests: number;
  forbiddenDiscoveryRequests: string[];
}

function initialState(): QuotaBackendState {
  return {
    quota: {
      role_id: roleId,
      role_name: 'Analysis',
      daily_query_limit: 100,
      daily_execution_limit: 50,
      daily_export_limit: 5,
    },
    listRequests: 0,
    mutationBodies: [],
    mutationRequests: 0,
    forbiddenDiscoveryRequests: [],
  };
}

async function installQuotaOnlyBackend(page: Page, state: QuotaBackendState) {
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname;
    if (path.includes('/admin/roles') || path.includes('/admin/sso/')) {
      state.forbiddenDiscoveryRequests.push(path);
    }
  });
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'chunk-09-admin',
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
  await page.route('**/api/v1/sessions', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [],
        pagination: { page: 1, page_size: 10, total_entries: 0, total_pages: 0 },
      }),
    })
  );
  await page.route('**/api/v1/admin/quotas/status', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: [] }),
    })
  );
  await page.route('**/api/v1/admin/quotas', (route) => {
    state.listRequests += 1;
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ quotas: state.quota ? [state.quota] : [] }),
    });
  });
}

async function expectInsideViewport(page: Page, selector: Locator) {
  const box = await selector.boundingBox();
  const viewport = page.viewportSize();
  expect(box).not.toBeNull();
  expect(viewport).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport!.width);
}

for (const viewport of [
  { name: 'desktop', width: 1280, height: 900 },
  { name: '375px', width: 375, height: 812 },
]) {
  test(`save pending recovery survives reload without clipping at ${viewport.name}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    const state = initialState();
    await installQuotaOnlyBackend(page, state);
    await page.route(`**/api/v1/admin/quotas/${roleId}`, async (route) => {
      state.mutationRequests += 1;
      state.mutationBodies.push(route.request().postDataJSON());
      state.quota = { ...state.quota!, daily_query_limit: 4 };
      await route.fulfill({
        status: state.mutationRequests === 1 ? 503 : 200,
        contentType: 'application/json',
        body: JSON.stringify(
          state.mutationRequests === 1 ? pendingResponse : state.quota
        ),
      });
    });

    await page.goto('/admin/quotas?lng=en');
    await page.locator('button[title="Edit"]:visible').click();
    await page.getByLabel('Daily Query Limit').fill('4');
    await page.getByRole('button', { name: 'Save' }).click();

    const recovery = page.getByRole('alert', {
      name: 'Quota change needs synchronization',
    });
    await expect(recovery).toBeVisible();
    await expect(page.getByText('Changes saved successfully')).toHaveCount(0);
    await expectInsideViewport(page, recovery);
    expect(state.listRequests).toBeGreaterThanOrEqual(2);

    await page.reload();
    await expect(recovery).toBeVisible();
    await expect(
      page.locator('bdi:visible').filter({ hasText: /^4$/ }).first()
    ).toBeVisible();
    await recovery.getByRole('button', { name: 'Retry' }).click();

    await expect(recovery).toHaveCount(0);
    await expect(page.getByText('Changes saved successfully')).toBeVisible();
    expect(state.mutationRequests).toBe(2);
    expect(state.mutationBodies[1]).toEqual(state.mutationBodies[0]);
    expect(state.forbiddenDiscoveryRequests).toEqual([]);
  });
}

test('Arabic delete pending recovery survives reload without clipping at 768px', async ({
  page,
}) => {
  await page.setViewportSize({ width: 768, height: 1024 });
  const state = initialState();
  await installQuotaOnlyBackend(page, state);
  await page.route(`**/api/v1/admin/quotas/${roleId}`, async (route) => {
    state.mutationRequests += 1;
    state.quota = null;
    await route.fulfill({
      status: state.mutationRequests === 1 ? 503 : 204,
      contentType: 'application/json',
      body: state.mutationRequests === 1 ? JSON.stringify(pendingResponse) : '',
    });
  });
  page.on('dialog', (dialog) => dialog.accept());

  await page.goto('/admin/quotas?lng=ar');
  await page.getByTitle('إعادة إلى غير مقيد').first().click();

  const recovery = page.getByRole('alert', {
    name: 'تغيير الحصة يحتاج إلى مزامنة',
  });
  await expect(recovery).toBeVisible();
  await expect(page.getByText('تم حذف تكوين الحصص بنجاح')).toHaveCount(0);
  await expectInsideViewport(page, recovery);
  expect(state.listRequests).toBeGreaterThanOrEqual(2);

  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(recovery).toBeVisible();
  await expect(page.getByText('لا توجد تكوينات حصص بعد.')).toBeVisible();
  await recovery.getByRole('button', { name: 'إعادة المحاولة' }).click();

  await expect(recovery).toHaveCount(0);
  await expect(page.getByText('تم حذف تكوين الحصص بنجاح')).toBeVisible();
  expect(state.mutationRequests).toBe(2);
  expect(state.forbiddenDiscoveryRequests).toEqual([]);
});
