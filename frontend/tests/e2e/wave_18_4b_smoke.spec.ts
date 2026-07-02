import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const EVIDENCE_DIR = path.resolve(process.cwd(), '../audit/wave-18');

test.describe('Wave 18.4b — Frontend Smoke Verification', () => {
  test.beforeAll(() => {
    if (!fs.existsSync(EVIDENCE_DIR)) {
      fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
    }
  });

  test.beforeEach(async ({ page }) => {
    // 1. Mock Auth
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'admin-uuid',
          username: 'admin',
          display_name: 'Platform Administrator',
          role: 'admin',
          permissions: [
            'admin.audit.verify',
            'admin.sso.manage',
            'admin.roles.manage',
            'admin.quotas.manage',
            'admin.security.manage'
          ]
        })
      });
    });

    // 2. Mock Connections
    await page.route('**/api/v1/connections', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          connections: [
            {
              id: 'conn-pg-1',
              name: 'PostgreSQL Analytics',
              dialect: 'postgresql',
              health_status: 'healthy',
              introspection_status: 'success',
              lifecycle_state: 'active'
            }
          ]
        })
      });
    });

    // 3. Mock Sessions
    await page.route('**/api/v1/sessions', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [],
          pagination: { page: 1, page_size: 10, total_entries: 0, total_pages: 0 }
        })
      });
    });

    // 4. Mock Roles
    await page.route('**/api/v1/admin/roles', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          roles: [
            { id: 'admin-role-id', name: 'Admin', permissions: ['*'] },
            { id: 'user-role-id', name: 'User', permissions: [] }
          ]
        })
      });
    });

    // 5. Mock Quotas list
    await page.route('**/api/v1/admin/quotas', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          quotas: [
            {
              role_id: 'admin-role-id',
              role_name: 'Admin',
              daily_query_limit: 100,
              daily_execution_limit: 50,
              daily_export_limit: 10
            }
          ]
        })
      });
    });

    // 6. Mock Quota status
    await page.route('**/api/v1/admin/quotas/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: [
            {
              role_id: 'admin-role-id',
              role_name: 'Admin',
              dimensions: {
                queries: { limit: 100, used: 45, remaining: 55 },
                executions: { limit: 50, used: 20, remaining: 30 },
                exports: { limit: 10, used: 2, remaining: 8 }
              },
              reset_at: '2026-07-03T12:00:00Z'
            }
          ]
        })
      });
    });

    // 7. Mock Detection config
    await page.route('**/api/v1/admin/detection/config', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          block_confidence: 0.8,
          flag_confidence: 0.5
        })
      });
    });

    // 8. Mock Audit status
    await page.route('**/api/v1/admin/audit/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_entries: 105,
          last_verification: {
            verified: true,
            entries_checked: 105,
            verified_at: '2026-06-07T03:00:00Z'
          }
        })
      });
    });

    // 9. Mock Audit retention
    await page.route('**/api/v1/admin/audit/retention', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          retention_months: 6,
          last_purge_at: '2026-06-07T03:00:00Z',
          purged_count: 12
        })
      });
    });

    // 10. Mock Audit entries (search)
    await page.route('**/api/v1/admin/audit/entries*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          entries: [
            {
              sequence_number: 1,
              timestamp: '2026-07-02T12:00:00Z',
              actor_identity: 'admin',
              action_type: 'user.login',
              resource_type: 'user',
              resource_id: 'admin-uuid',
              outcome: 'success',
              context: {}
            },
            {
              sequence_number: 2,
              timestamp: '2026-07-02T12:05:00Z',
              actor_identity: 'admin',
              action_type: 'query.submit',
              resource_type: 'query',
              resource_id: 'query-uuid',
              outcome: 'hostile_input_blocked',
              context: {}
            }
          ],
          pagination: { page: 1, page_size: 10, total_entries: 2, total_pages: 1 }
        })
      });
    });
  });

  test('T-896: Arabic/RTL desktop browser smoke for /admin/quotas (UC-11)', async ({ page }) => {
    await page.goto('/admin/quotas?lng=ar');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    await expect(page.locator('html')).toHaveAttribute('lang', 'ar');

    // Confirm Arabic texts and no English fallback
    const title = page.locator('h1');
    await expect(title).toContainText('حصص الأدوار');
    await expect(page.getByText('الحد اليومي للاستعلامات').first()).toBeVisible();
    await expect(page.getByText('الحد اليومي لتنفيذ SQL').first()).toBeVisible();
    await expect(page.getByText('الحد اليومي لتصدير سجل التدقيق').first()).toBeVisible();
    await expect(page.getByText('حالة استهلاك الحصص').first()).toBeVisible();

    // Verify list element layout alignment
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'desktop-admin-quotas-ar.png'), fullPage: true });
  });

  test('T-897: Arabic/RTL query flow smoke for UC-12, UC-13, UC-14', async ({ page }) => {
    // Go to query submit page (main workspace page) in Arabic
    await page.goto('/?lng=ar');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');

    // Subtest: Quota Exceeded (UC-12)
    // Setup temporary route interceptor for 429
    await page.route('**/api/v1/query/submit', async (route) => {
      await route.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'quota_exceeded',
          message_key: 'error.quota_exceeded',
          reset_at: '2026-07-03T12:00:00Z'
        })
      });
    });

    const textarea = page.locator('textarea');
    await expect(textarea).toBeVisible();
    await expect(textarea).toBeEnabled({ timeout: 10_000 });
    await textarea.fill('SELECT * FROM actor;');
    // Press submit
    await page.getByTestId('prompt-send').click();

    // Wait for the banner
    await expect(page.locator('[data-testid="quota-exceeded-banner"]').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('تم الوصول إلى الحد اليومي للاستعلامات. يرجى المحاولة مرة أخرى غداً.')).toBeVisible();
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'desktop-query-flow-quota-exceeded-ar.png') });

    // Subtest: Hostile Input Blocked (UC-13)
    // Setup temporary route interceptor for 400 hostile
    await page.route('**/api/v1/query/submit', async (route) => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'hostile_input_blocked',
          message_key: 'error.hostile_input_blocked'
        })
      });
    });

    await expect(textarea).toBeEnabled({ timeout: 10_000 });
    await textarea.fill('DROP DATABASE querycraft;');
    await page.getByTestId('prompt-send').click();

    await expect(page.locator('[data-testid="hostile-input-blocked-banner"]').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('تم حظر هذا الطلب لأنه يحتوي على محتوى ينتهك سياسة الأمان.')).toBeVisible();

    // Verify no input echo in code block (SQL is not shown in SqlDisplay/ResultTable)
    await expect(page.locator('.sql-display')).not.toBeVisible();
    await expect(page.locator('.result-table')).not.toBeVisible();
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'desktop-query-flow-hostile-blocked-ar.png') });

    // Subtest: Detection Config (UC-14)
    await page.goto('/admin/detection?lng=ar');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    await expect(page.locator('h1')).toContainText('كشف المدخلات المعادية');
    await expect(page.getByText('حد الحظر (0.0 - 1.0)')).toBeVisible();
    await expect(page.getByText('حد الإبلاغ (0.0 - 1.0)')).toBeVisible();
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'desktop-admin-detection-ar.png'), fullPage: true });
  });

  test('T-898: Arabic/RTL audit surfaces smoke (UC-15, UC-16, UC-17, UC-18)', async ({ page }) => {
    await page.goto('/admin/audit?lng=ar');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');

    // Confirm elements on AdminAuditPage
    await expect(page.locator('h1')).toContainText('التحقق من سلامة سجل التدقيق');

    // 1. Audit search filters (UC-15)
    await expect(page.getByText('بحث في سجل التدقيق').or(page.locator('form label').first())).toBeVisible();
    await expect(page.locator('table')).toBeVisible();

    // 2. Export button (UC-16)
    const csvButton = page.getByRole('button', { name: 'تصدير CSV' });
    await expect(csvButton).toBeVisible();

    // Set up route mock for POST /api/v1/admin/audit/export
    let exportRequestBody: { format?: string } = {};
    await page.route('**/api/v1/admin/audit/export', async (route) => {
      exportRequestBody = (route.request().postDataJSON() as { format?: string }) || {};
      await route.fulfill({
        status: 200,
        contentType: 'text/csv',
        body: 'sequence_number,timestamp,actor_identity,action_type,resource_type,resource_id,outcome\n1,2026-07-02T12:00:00Z,admin,user.login,user,admin-uuid,success'
      });
    });

    // Trigger CSV export and assert download happens
    const downloadPromise = page.waitForEvent('download');
    await csvButton.click();
    const download = await downloadPromise;

    // Assert request body details
    expect(exportRequestBody.format).toBeDefined();
    expect(exportRequestBody.format).toBe('csv');

    // Assert suggested filename ends in .csv
    expect(download.suggestedFilename().endsWith('.csv')).toBe(true);

    // 3. Retention Panel (UC-17)
    await expect(page.getByText('حفظ سجلات التدقيق')).toBeVisible();
    await expect(page.getByText('فترة الحفظ')).toBeVisible();
    await expect(page.getByText('عدد الإدخالات المطهّرة')).toBeVisible();

    // Save screenshots for audit page
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'desktop-audit-search-ar.png'), fullPage: true });
  });

  test('T-899: Mobile viewport responsiveness at 375px and 768px', async ({ page }) => {
    const viewports = [
      { name: '375px', width: 375, height: 812 },
      { name: '768px', width: 768, height: 1024 }
    ];

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });

      // 1. AdminQuotasPage (UC-11)
      await page.goto('/admin/quotas?lng=en');
      await expect(page.locator('h1')).toContainText('Role Quotas');
      await page.screenshot({ path: path.join(EVIDENCE_DIR, `mobile-${vp.name}-admin-quotas.png`), fullPage: true });

      // 2. AdminDetectionPage (UC-14)
      await page.goto('/admin/detection?lng=en');
      await expect(page.locator('h1')).toContainText('Hostile Input Detection');
      await page.screenshot({ path: path.join(EVIDENCE_DIR, `mobile-${vp.name}-admin-detection.png`), fullPage: true });

      // 3. AdminAuditPage (UC-15, UC-17, UC-18)
      await page.goto('/admin/audit?lng=en');
      await expect(page.locator('h1')).toContainText('Audit Log');
      await page.screenshot({ path: path.join(EVIDENCE_DIR, `mobile-${vp.name}-admin-audit.png`), fullPage: true });
    }
  });
});
