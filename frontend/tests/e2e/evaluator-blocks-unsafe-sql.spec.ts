/**
 * E2E spec T-156: evaluator blocks unsafe SQL — full sweep.
 *
 * Covers all 4 violation categories end-to-end through mocked backend responses:
 *   A. data-modifying SQL (read_only) — DELETE/UPDATE/INSERT/TRUNCATE/DROP/ALTER
 *   B. schema-invalid SQL (schema_validation) — unknown table / column
 *   C. multi-statement SQL (single_statement)
 *   D. unsafe-pattern SQL (unsafe_pattern) — pg_sleep, pg_read_file, etc.
 *
 * MOCKED at Playwright level (page.route). After backend StubLLM supports
 * deterministic keyword-based SQL (T-210 / CI infra), this can be upgraded
 * to full-stack E2E by removing the mocks.
 */

import { test, expect, type Page } from '@playwright/test';
import {
  mockSubmitEvaluatorRejectedWithViolations,
  mockHistoryEmpty,
} from './helpers/mock-backend';

const USERNAME = process.env.E2E_TEST_USERNAME ?? 'e2e_user';
const PASSWORD = process.env.E2E_TEST_PASSWORD ?? 'e2e_password_123';

async function signIn(page: Page) {
  await page.goto('/');
  await expect(page).toHaveURL(/\/sign-in/, { timeout: 5_000 });
  await page.getByLabel(/username/i).fill(USERNAME);
  await page.getByLabel(/password/i).fill(PASSWORD);
  await page.getByRole('button', { name: /sign\s*in/i }).click();
  await expect(page).toHaveURL(/\/(ask)?\/?$/);
}

/**
 * Shared assertions for any evaluator-rejection scenario:
 * 1. Banner is visible inside <main>.
 * 2. Banner contains the expected i18n message (not raw key).
 * 3. Result table is NOT shown.
 * 4. History endpoint returns empty (no row written).
 */
async function assertRejectionUI(
  page: Page,
  opts: { expectedText: RegExp | string; historyShouldBeEmpty?: boolean }
) {
  const banner = page.locator('main').getByRole('alert');
  await expect(banner).toBeVisible({ timeout: 5_000 });
  await expect(banner).toContainText(opts.expectedText);

  // Result table must NOT appear
  await expect(page.getByRole('table')).not.toBeVisible();

  if (opts.historyShouldBeEmpty) {
    // Navigate to history and assert no new row
    await page.getByRole('link', { name: /history/i }).click();
    await expect(page).toHaveURL(/\/history/);
    await expect(page.getByText(/no accepted queries yet/i)).toBeVisible({ timeout: 5_000 });
  }
}

test.describe('T-156: evaluator blocks unsafe SQL — full sweep', () => {
  test.beforeEach(async ({ page }) => {
    await mockHistoryEmpty(page);
  });

  // ── Group A: data-modifying SQL ──
  const dataModifyingStatements = ['DELETE', 'UPDATE', 'INSERT', 'TRUNCATE', 'DROP', 'ALTER'];
  for (const statement of dataModifyingStatements) {
    test(`read_only rejection for ${statement}`, async ({ page }) => {
      await mockSubmitEvaluatorRejectedWithViolations(page, [
        {
          rule: 'read_only',
          message_key: 'evaluator.violation.dataModifying',
          message_params: { statement },
        },
      ]);
      await signIn(page);

      await page.getByPlaceholder(/Ask a question/i).fill(`Do a ${statement}`);
      await page.getByRole('button', { name: /^ask$/i }).click();

      await assertRejectionUI(page, {
        expectedText: /Write operations are blocked/i,
        historyShouldBeEmpty: true,
      });
    });
  }

  // ── Group B: schema-invalid SQL ──
  test('schema_validation rejection for unknown table', async ({ page }) => {
    await mockSubmitEvaluatorRejectedWithViolations(page, [
      {
        rule: 'schema_validation',
        message_key: 'evaluator.violation.unknownTable',
        message_params: { table: 'nonexistent_table' },
      },
    ]);
    await signIn(page);

    await page.getByPlaceholder(/Ask a question/i).fill('Query from fake table');
    await page.getByRole('button', { name: /^ask$/i }).click();

    await assertRejectionUI(page, {
      expectedText: /Schema mismatch: nonexistent_table/i,
      historyShouldBeEmpty: true,
    });
  });

  test('schema_validation rejection for unknown column', async ({ page }) => {
    await mockSubmitEvaluatorRejectedWithViolations(page, [
      {
        rule: 'schema_validation',
        message_key: 'evaluator.violation.unknownColumn',
        message_params: { column: 'fake_col', table: 'customer' },
      },
    ]);
    await signIn(page);

    await page.getByPlaceholder(/Ask a question/i).fill('Select fake column');
    await page.getByRole('button', { name: /^ask$/i }).click();

    await assertRejectionUI(page, {
      expectedText: /Schema mismatch: customer/i,
      historyShouldBeEmpty: true,
    });
  });

  // ── Group C: multi-statement SQL ──
  test('single_statement rejection for multiple statements', async ({ page }) => {
    await mockSubmitEvaluatorRejectedWithViolations(page, [
      {
        rule: 'single_statement',
        message_key: 'evaluator.violation.multiStatement',
      },
    ]);
    await signIn(page);

    await page.getByPlaceholder(/Ask a question/i).fill('Run two selects');
    await page.getByRole('button', { name: /^ask$/i }).click();

    await assertRejectionUI(page, {
      expectedText: /Only one statement per query is allowed/i,
      historyShouldBeEmpty: true,
    });
  });

  // ── Group D: unsafe-pattern SQL (FR-010f catalog sweep) ──
  const unsafePatterns = [
    'pg_sleep',
    'pg_read_file',
    'pg_ls_dir',
    'pg_terminate_backend',
    'lo_import',
    'COPY ... FROM PROGRAM',
    'dblink',
    'LISTEN',
    'SET ROLE',
  ];
  for (const pattern of unsafePatterns) {
    test(`unsafe_pattern rejection for ${pattern}`, async ({ page }) => {
      await mockSubmitEvaluatorRejectedWithViolations(page, [
        {
          rule: 'unsafe_pattern',
          message_key: 'evaluator.violation.unsafePattern',
          message_params: { pattern },
        },
      ]);
      await signIn(page);

      await page.getByPlaceholder(/Ask a question/i).fill(`Use ${pattern}`);
      await page.getByRole('button', { name: /^ask$/i }).click();

      await assertRejectionUI(page, {
        expectedText: new RegExp(`Unsafe pattern detected: ${pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`),
        historyShouldBeEmpty: true,
      });
    });
  }

  // ── Multiple violations ordering ──
  test('multiple violations render in order', async ({ page }) => {
    await mockSubmitEvaluatorRejectedWithViolations(page, [
      {
        rule: 'read_only',
        message_key: 'evaluator.violation.dataModifying',
        message_params: { statement: 'UPDATE' },
      },
      {
        rule: 'schema_validation',
        message_key: 'evaluator.violation.unknownTable',
        message_params: { table: 'ghost_table' },
      },
      {
        rule: 'unsafe_pattern',
        message_key: 'evaluator.violation.unsafePattern',
        message_params: { pattern: 'pg_sleep' },
      },
    ]);
    await signIn(page);

    await page.getByPlaceholder(/Ask a question/i).fill('Bad query with many issues');
    await page.getByRole('button', { name: /^ask$/i }).click();

    const banner = page.locator('main').getByRole('alert');
    await expect(banner).toBeVisible({ timeout: 5_000 });

    // Assert each violation message is rendered
    await expect(banner).toContainText(/Write operations are blocked/i);
    await expect(banner).toContainText(/Schema mismatch: ghost_table/i);
    await expect(banner).toContainText(/Unsafe pattern detected: pg_sleep/i);

    await expect(page.getByRole('table')).not.toBeVisible();
  });
});
