import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';
import { signInLocalUser } from './helpers/auth';

const USERNAME = process.env.E2E_ADMIN_USERNAME || 'admin';
const PASSWORD = process.env.E2E_ADMIN_PASSWORD;
const EVIDENCE_DIR = path.resolve('../specs/005-sso-rbac-row-column-security/evidence');

async function signIn(page: Page) {
  if (!PASSWORD) {
    throw new Error('E2E_ADMIN_PASSWORD environment variable is not defined.');
  }
  await signInLocalUser(page, { username: USERNAME, password: PASSWORD });
}

test.describe('Wave 17.3o — Policy Editor and Masked Column Indicator', () => {
  test.beforeAll(() => {
    if (!fs.existsSync(EVIDENCE_DIR)) {
      fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
    }
  });

  test.beforeEach(async ({ page }) => {
    test.skip(!PASSWORD, 'Skipping E2E tests because E2E_ADMIN_PASSWORD is not provided.');

    // Mock user connections
    await page.route('**/connections', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          connections: [
            {
              id: 'conn-e2e-1',
              display_name: 'PostgreSQL Pagila',
              database_type: 'postgresql'
            }
          ]
        })
      });
    });

    // Mock admin connections
    await page.route('**/admin/connections', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          connections: [
            {
              id: 'conn-e2e-1',
              display_name: 'PostgreSQL Pagila',
              database_type: 'postgresql'
            }
          ]
        })
      });
    });

    // Mock admin roles
    await page.route('**/admin/roles', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          roles: []
        })
      });
    });

    // Mock schema
    await page.route('**/admin/connections/conn-e2e-1/schema', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tables: [
            {
              table_name: 'customer',
              columns: [
                { column_name: 'customer_id', data_type: 'integer' },
                { column_name: 'email', data_type: 'character varying' },
                { column_name: 'first_name', data_type: 'character varying' },
                { column_name: 'last_name', data_type: 'character varying' }
              ]
            }
          ]
        })
      });
    });
  });

  test('Verify Masked Column Indicator renders in Result Table (EN & AR)', async ({ page }) => {
    // Mock result execution with masked columns
    await page.route('**/query/submit', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          kind: 'result',
          attempt_id: 'attempt-mock-masked-1',
          question: 'Show customer details',
          generated_sql: 'SELECT customer_id, email FROM customer;',
          columns: [
            { name: 'customer_id', type: 'integer' },
            { name: 'email', type: 'text', masked: true }
          ],
          rows: [
            [1, '***']
          ],
          row_count: 1,
          attempt_number: 1,
          is_last_auto_retry: false
        })
      });
    });

    await signIn(page);

    // 1. English Verification
    await page.goto('/?lng=en');
    await expect(page.locator('textarea')).toBeEnabled({ timeout: 10_000 });
    await page.locator('textarea').fill('Show customer details');
    await page.getByTestId('prompt-send').click({ force: true });
    
    // Wait for masked indicator
    await expect(page.getByText('Masked')).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'masked-indicator-en.png'), fullPage: true });

    // 2. Arabic Verification
    await page.goto('/?lng=ar');
    await expect(page.locator('textarea')).toBeEnabled({ timeout: 10_000 });
    await page.locator('textarea').fill('Show customer details');
    await page.getByTestId('prompt-send').click({ force: true });
    
    // Wait for Arabic masked indicator "محجوب"
    await expect(page.getByText('محجوب')).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'masked-indicator-ar.png'), fullPage: true });
  });

  test('Verify Policy Editor renders correctly (EN & AR)', async ({ page }) => {
    await signIn(page);

    // 1. English Policy Editor
    await page.goto('/admin/roles?lng=en');
    await expect(page.getByRole('button', { name: /add role/i })).toBeVisible({ timeout: 10_000 });
    await page.getByRole('button', { name: /add role/i }).click();

    // Fill role form
    await page.locator('#roleName').fill('Analyst_EN');
    await page.locator('#rolePriority').fill('50');
    await page.locator('#roleDescription').fill('Analyst role with masked columns');

    // Open Policy Editor
    await page.getByRole('button', { name: /add connection policy/i }).click();

    // Select connection
    await page.locator('#policyConnection').selectOption('conn-e2e-1');
    
    // Check table and columns
    const tableCheckbox = page.locator('[data-testid="table-checkbox-customer"]');
    await expect(tableCheckbox).toBeVisible({ timeout: 10_000 });
    await tableCheckbox.check();

    const emailCheckbox = page.locator('[data-testid="column-checkbox-customer-email"]');
    await expect(emailCheckbox).toBeVisible({ timeout: 10_000 });
    await emailCheckbox.check();

    // Add Row-Level Filter
    await page.getByRole('button', { name: /add row filter/i }).click();
    await page.locator('select').filter({ has: page.locator('option[value="customer"]') }).first().selectOption('customer');
    await page.locator('input[placeholder*="department_id"]').fill('customer_id = 1');

    // Add Column Mask
    await page.getByRole('button', { name: /add column mask/i }).click();
    await page.locator('select').filter({ has: page.locator('option[value="customer"]') }).nth(1).selectOption('customer');
    await page.locator('[data-testid="mask-column-select-customer"]').selectOption('email');

    // Take English Policy Editor Screenshot
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'policy-editor-en.png'), fullPage: true });

    // Click Save Connection Policy
    await page.getByRole('button', { name: /save/i }).first().click();

    // Click Cancel Role creation to reset
    await page.getByRole('button', { name: /cancel/i }).click();

    // 2. Arabic Policy Editor (RTL)
    await page.goto('/admin/roles?lng=ar');
    await expect(page.getByRole('button', { name: /إضافة دور/i })).toBeVisible({ timeout: 10_000 });
    await page.getByRole('button', { name: /إضافة دور/i }).click();

    // Open Policy Editor in Arabic
    await page.getByRole('button', { name: /إضافة سياسة اتصال/i }).click();
    await page.locator('#policyConnection').selectOption('conn-e2e-1');

    // Check table checkbox (customer)
    const tableCheckboxAr = page.locator('[data-testid="table-checkbox-customer"]');
    await expect(tableCheckboxAr).toBeVisible({ timeout: 10_000 });
    await tableCheckboxAr.check();

    const emailCheckboxAr = page.locator('[data-testid="column-checkbox-customer-email"]');
    await expect(emailCheckboxAr).toBeVisible({ timeout: 10_000 });
    await emailCheckboxAr.check();

    // Add Row-Level Filter in Arabic
    await page.getByRole('button', { name: /إضافة عامل تصفية صف/i }).click();
    await page.locator('select').filter({ has: page.locator('option[value="customer"]') }).first().selectOption('customer');
    await page.locator('input[placeholder*="department_id"]').fill('customer_id = 1');

    // Add Column Mask in Arabic
    await page.getByRole('button', { name: /إضافة قناع عمود/i }).click();
    await page.locator('select').filter({ has: page.locator('option[value="customer"]') }).nth(1).selectOption('customer');
    await page.locator('[data-testid="mask-column-select-customer"]').selectOption('email');

    // Take Arabic Policy Editor Screenshot (Verify RTL alignment)
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'policy-editor-ar.png'), fullPage: true });
  });
});
