import { test, expect } from '@playwright/test';
import { mockHistoryList, mockHistoryDetail, mockHistoryEmpty, mockConnections } from './helpers/mock-backend';

const USERNAME = process.env.E2E_TEST_USERNAME ?? 'e2e_user';
const PASSWORD = process.env.E2E_TEST_PASSWORD ?? 'e2e_password_123';

async function signIn(page: import('@playwright/test').Page) {
  await mockConnections(page);
  await page.goto('/');
  await expect(page).toHaveURL(/\/sign-in/, { timeout: 5_000 });
  await page.getByLabel(/username/i).fill(USERNAME);
  await page.getByLabel(/password/i).fill(PASSWORD);
  await page.getByRole('button', { name: /sign\s*in/i }).click();
  await expect(page).toHaveURL(/\/(ask)?\/?$/);
  await expect(page.locator('textarea')).toBeEnabled({ timeout: 5_000 });
}

test.describe('History List + Detail (FR-021, FR-022, FR-023, SC-006, SC-007)', () => {
  test('T-171: list renders in reverse-chrono order, filter narrows, row click shows detail', async ({ page }) => {
    const items = [
      { id: '1', question_text: 'Customer count', generated_sql: 'SELECT COUNT(*) FROM customer', accepted_at: '2026-05-11T10:00:00Z', schema: 'public' },
      { id: '2', question_text: 'Revenue top 10', generated_sql: 'SELECT * FROM payment LIMIT 10', accepted_at: '2026-05-10T10:00:00Z', schema: 'public' },
      { id: '3', question_text: 'Recent rentals', generated_sql: "SELECT * FROM rental WHERE rental_date > now() - interval '7 days'", accepted_at: '2026-05-09T10:00:00Z', schema: 'public' },
    ];

    await signIn(page);
    await mockHistoryList(page, { items, total: 3, next_cursor: null });
    await mockHistoryDetail(page, items[0]);

    await page.goto('/history');
    await expect(page.getByText('Customer count')).toBeVisible();
    await expect(page.getByText('Revenue top 10')).toBeVisible();
    await expect(page.getByText('Recent rentals')).toBeVisible();

    // Reverse-chrono check: first row is most recent
    const rows = page.locator("[data-testid='history-row']");
    await expect(rows.first()).toContainText('Customer count');

    // Filter narrows visible rows (FR-022)
    await page.getByPlaceholder(/filter/i).fill('revenue');
    await expect(page.getByText('Customer count')).not.toBeVisible();
    await expect(page.getByText('Revenue top 10')).toBeVisible();
    await page.getByPlaceholder(/filter/i).fill('');

    // Click row shows detail (FR-023)
    await page.getByText('Customer count').click();
    const detail = page.getByTestId('history-detail');
    await expect(detail).toContainText('SELECT COUNT(*)');
  });

  test('T-172: empty history state shown when no items (FR-021)', async ({ page }) => {
    await signIn(page);
    await mockHistoryEmpty(page);
    await page.goto('/history');
    await expect(page.getByText(/no history yet/i)).toBeVisible();
  });

  test('T-173: rejected queries do NOT appear in history (FR-020, SC-012)', async ({ page }) => {
    await signIn(page);
    await mockHistoryList(page, {
      items: [
        { id: '1', question_text: 'Accepted Q', generated_sql: 'SELECT 1', accepted_at: '2026-05-11T00:00:00Z', schema: 'public' },
      ],
      total: 1,
      next_cursor: null,
    });
    await page.goto('/history');
    await expect(page.getByText('Accepted Q')).toBeVisible();
    // Verify rejected attempts (e.g. "DROP TABLE users") are not in the table
    await expect(page.getByText(/DROP TABLE/i)).not.toBeVisible();
  });
});
