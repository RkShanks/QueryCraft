import { test, expect } from '@playwright/test';
import * as path from 'path';
import { signInLocalUser } from './helpers/auth';

const EVIDENCE_DIR = path.resolve('../specs/004-arabic-rtl-verification-polish/evidence/wave-16.3');

test.describe('Wave 16.3 — Cross-Language DB Smoke Testing', () => {
  test('Execute Arabic prompts against PostgreSQL, MySQL, and MSSQL real databases', async ({ page }) => {
    // Increase timeout to 3 minutes to accommodate rate-limit spacing
    test.setTimeout(180_000);

    // Step 1: Sign in
    console.log('Signing in...');
    await signInLocalUser(page);
    await expect(page.getByTestId('database-selector-trigger')).toBeVisible({ timeout: 10_000 });
    console.log('Sign in successful. Landed on workspace page.');

    // --- PostgreSQL Pagila Smoke Test ---
    console.log('Starting PostgreSQL Pagila smoke test...');
    // Open selector and select PostgreSQL
    await page.getByTestId('database-selector-trigger').click();
    await page.getByRole('option', { name: 'PostgreSQL Pagila' }).click();

    // Now textarea should be enabled
    const pgInput = page.locator('textarea');
    await expect(pgInput).toBeEnabled({ timeout: 5_000 });
    // Fill prompt
    await pgInput.fill('أظهر لي جميع الممثلين');
    await page.getByTestId('prompt-send').click({ force: true });

    // Wait for card
    const pgCard = page.locator('[data-testid="assistant-response-card"]').first();
    await expect(pgCard).toBeVisible({ timeout: 45_000 });
    await expect(pgCard.getByText('PostgreSQL Pagila')).toBeVisible();
    await expect(pgCard.getByText('PostgreSQL', { exact: true })).toBeVisible();

    // Expand SQL display
    await pgCard.getByTestId('sql-toggle-btn').click();
    const pgSqlPre = pgCard.locator('[data-testid="sql-code-block"] pre');
    await expect(pgSqlPre).toContainText('SELECT', { timeout: 15_000 });

    // Verify SQL dialect markers
    const pgSql = await pgSqlPre.textContent();
    console.log('PG Generated SQL:', pgSql);
    expect(pgSql?.toLowerCase()).toContain('actor');

    // Take screenshot
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'pg-arabic-smoke.png'), fullPage: true });
    console.log('PostgreSQL smoke test completed successfully.');

    // Add a 25-second delay to prevent rate limits
    console.log('Waiting 25 seconds to avoid rate limits...');
    await page.waitForTimeout(25000);

    // --- MySQL Sakila Smoke Test ---
    console.log('Starting MySQL Sakila smoke test...');
    await page.goto('/');
    await page.waitForURL(/\/(ask)?\/?$/);
    await expect(page.getByTestId('database-selector-trigger')).toBeVisible({ timeout: 10_000 });

    // Open selector and select MySQL
    await page.getByTestId('database-selector-trigger').click();
    await page.getByRole('option', { name: 'MySQL Sakila' }).click();

    // Fill prompt
    const mysqlInput = page.locator('textarea');
    await expect(mysqlInput).toBeEnabled({ timeout: 5_000 });
    await mysqlInput.fill('أظهر لي جميع الممثلين');
    await page.getByTestId('prompt-send').click({ force: true });

    // Wait for card
    const mysqlCard = page.locator('[data-testid="assistant-response-card"]').first();
    await expect(mysqlCard).toBeVisible({ timeout: 45_000 });
    await expect(mysqlCard.getByText('MySQL Sakila')).toBeVisible();
    await expect(mysqlCard.getByText('MySQL', { exact: true })).toBeVisible();

    // Expand SQL display
    await mysqlCard.getByTestId('sql-toggle-btn').click();
    const mysqlSqlPre = mysqlCard.locator('[data-testid="sql-code-block"] pre');
    await expect(mysqlSqlPre).toContainText('SELECT', { timeout: 15_000 });

    // Verify SQL dialect markers
    const mysqlSql = await mysqlSqlPre.textContent();
    console.log('MySQL Generated SQL:', mysqlSql);
    expect(mysqlSql?.toLowerCase()).toContain('actor');

    // Take screenshot
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'mysql-arabic-smoke.png'), fullPage: true });
    console.log('MySQL smoke test completed successfully.');

    // Add a 25-second delay to prevent rate limits
    console.log('Waiting 25 seconds to avoid rate limits...');
    await page.waitForTimeout(25000);

    // --- MSSQL AdventureWorks Smoke Test ---
    console.log('Starting MSSQL AdventureWorks smoke test...');
    await page.goto('/');
    await page.waitForURL(/\/(ask)?\/?$/);
    await expect(page.getByTestId('database-selector-trigger')).toBeVisible({ timeout: 10_000 });

    // Open selector and select MSSQL
    await page.getByTestId('database-selector-trigger').click();
    await page.getByRole('option', { name: 'MSSQL AdventureWorks' }).click();

    // Fill prompt
    const mssqlInput = page.locator('textarea');
    await expect(mssqlInput).toBeEnabled({ timeout: 5_000 });
    await mssqlInput.fill('أظهر لي جميع العملاء');
    await page.getByTestId('prompt-send').click({ force: true });

    // Wait for card
    const mssqlCard = page.locator('[data-testid="assistant-response-card"]').first();
    await expect(mssqlCard).toBeVisible({ timeout: 45_000 });
    await expect(mssqlCard.getByText('MSSQL AdventureWorks')).toBeVisible();
    await expect(mssqlCard.getByText('MS SQL Server', { exact: true })).toBeVisible();

    // Expand SQL display
    await mssqlCard.getByTestId('sql-toggle-btn').click();
    const mssqlSqlPre = mssqlCard.locator('[data-testid="sql-code-block"] pre');
    await expect(mssqlSqlPre).toContainText('SELECT', { timeout: 15_000 });

    // Verify SQL dialect markers
    const mssqlSql = await mssqlSqlPre.textContent();
    console.log('MSSQL Generated SQL:', mssqlSql);
    expect(mssqlSql?.toLowerCase()).toContain('customer');

    // Take screenshot
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'mssql-arabic-smoke.png'), fullPage: true });
    console.log('MSSQL smoke test completed successfully.');

    // --- History Metadata Smoke Test ---
    console.log('Starting History Metadata smoke test...');
    // Click History in sidebar
    await page.getByTestId('sidebar-nav-history').click({ force: true });
    await page.waitForURL(/\/history/);

    // Verify history table contains correct entries with localized metadata
    await expect(page.getByText('PostgreSQL Pagila').first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('MySQL Sakila').first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('MSSQL AdventureWorks').first()).toBeVisible({ timeout: 10_000 });

    // Take screenshot
    await page.screenshot({ path: path.join(EVIDENCE_DIR, 'history-metadata-smoke.png'), fullPage: true });
    console.log('History metadata smoke test completed successfully.');
  });
});
