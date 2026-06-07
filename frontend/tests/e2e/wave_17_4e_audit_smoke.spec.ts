import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const EVIDENCE_DIR = path.resolve('../specs/005-sso-rbac-row-column-security/evidence');

test.describe('Wave 17.4e — Audit Verification Page E2E', () => {
  test.beforeAll(() => {
    if (!fs.existsSync(EVIDENCE_DIR)) {
      fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
    }
  });

  test.beforeEach(async ({ page }) => {
    // Intercept/mock admin role & me calls to ensure admin permissions for navigation
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          username: 'admin',
          display_name: 'Platform Administrator',
          role: 'admin',
          permissions: ['admin.audit.verify', 'admin.sso.manage', 'admin.roles.manage']
        })
      });
    });

    await page.route('**/api/v1/connections', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ connections: [] })
      });
    });
  });

  test('Verify audit page initial status and successful verification (EN & AR)', async ({ page }) => {
    // 1. Initial status mock
    let verifyCallCount = 0;
    await page.route('**/api/v1/admin/audit/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_entries: 105,
          last_verification: verifyCallCount > 0 ? {
            verified: true,
            entries_checked: 105,
            verified_at: '2026-06-07T03:00:00Z'
          } : null
        })
      });
    });

    // 2. Verification mock
    await page.route('**/api/v1/admin/audit/verify', async (route) => {
      verifyCallCount++;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          verified: true,
          entries_checked: 105,
          verified_at: '2026-06-07T03:00:00Z'
        })
      });
    });

    // Navigate to Audit Verification page (EN)
    await page.goto('/admin/audit?lng=en');
    await expect(page.getByRole('heading', { name: /Tamper-Evident/i })).toBeVisible({ timeout: 10_000 });

    // Assert initial state renders correctly
    await expect(page.getByText('105').first()).toBeVisible();
    await expect(page.getByText(/never verified/i)).toBeVisible();

    // Take screenshot of initial state
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'audit-verify-initial-en.png'), fullPage: true });

    // Click "Verify Integrity"
    await page.getByRole('button', { name: /verify integrity/i }).click();

    // Verify success toast/status update
    await expect(page.getByText(/integrity verified successfully/i)).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/verified intact/i)).toBeVisible();

    // Take screenshot of verified state
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'audit-verify-success-en.png'), fullPage: true });

    // 3. Arabic and RTL Verification
    await page.goto('/admin/audit?lng=ar');
    await expect(page.getByRole('heading', { name: /التحقق من سلامة سجل التدقيق/i })).toBeVisible({ timeout: 10_000 });

    // Assert Arabic initial/success state renders
    await expect(page.getByText('105').first()).toBeVisible();
    await expect(page.getByText(/سليم وغير متلاعب به/i)).toBeVisible();

    // Take Arabic screenshot (Verify RTL mirroring)
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'audit-verify-success-ar.png'), fullPage: true });
  });

  test('Verify audit page broken chain behavior', async ({ page }) => {
    // 1. Initial status mock
    let statusCallCount = 0;
    await page.route('**/api/v1/admin/audit/status', async (route) => {
      statusCallCount++;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_entries: 105,
          last_verification: statusCallCount > 1 ? {
            verified: false,
            entries_checked: 42,
            first_break_at: 43,
            verified_at: '2026-06-07T03:05:00Z'
          } : null
        })
      });
    });

    // 2. Verification mock returning a broken chain
    await page.route('**/api/v1/admin/audit/verify', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          verified: false,
          entries_checked: 42,
          first_break_at: 43,
          verified_at: '2026-06-07T03:05:00Z'
        })
      });
    });

    await page.goto('/admin/audit?lng=en');
    await expect(page.getByRole('heading', { name: /Tamper-Evident/i })).toBeVisible({ timeout: 10_000 });

    // Click "Verify Integrity"
    await page.getByRole('button', { name: /verify integrity/i }).click();

    // Verify error toast/status update showing broken chain details
    await expect(page.getByText(/verification failed/i)).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/chain broken/i).first()).toBeVisible();
    await expect(page.getByText(/first break at sequence number/i)).toBeVisible();

    // Take screenshot of failed verification state
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'audit-verify-failed-en.png'), fullPage: true });
  });
});
