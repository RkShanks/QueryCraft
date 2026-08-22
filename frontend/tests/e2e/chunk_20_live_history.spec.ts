import { expect, test, type Page } from '@playwright/test';

/**
 * CHUNK-20 / IS-GAP-032 + IS-GAP-038 — live proof against the real stack.
 *
 * Real FastAPI HTTP + real PostgreSQL platform database with disposable
 * seeded users and accepted-query rows. No route mocking, no LLM call,
 * no source query. Credentials arrive via environment variables and are
 * never written into output.
 */

const LIVE_USERNAME = process.env.CHUNK20_LIVE_USERNAME;
const LIVE_PASSWORD = process.env.CHUNK20_LIVE_PASSWORD;

const PAGE_SIZE = 20;

async function signIn(page: Page): Promise<void> {
  await page.goto('/sign-in');
  await page.getByLabel(/username/i).fill(LIVE_USERNAME!);
  await page.getByLabel(/password/i).fill(LIVE_PASSWORD!);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL((url) => !url.pathname.includes('sign-in'));
}

test('searches the full dataset server-side with bounded pagination and exact totals', async ({
  page,
}) => {
  test.skip(
    !LIVE_USERNAME || !LIVE_PASSWORD,
    'CHUNK-20 disposable live credentials are required.'
  );
  await page.setViewportSize({ width: 1440, height: 900 });
  const historyRequests: string[] = [];
  page.on('request', (request) => {
    if (request.url().includes('/api/v1/history')) historyRequests.push(request.url());
  });

  await signIn(page);
  await page.goto('/history');
  const listPanel = page.getByTestId('history-list-panel');

  // Initial load: exactly one bounded request for the first page.
  await expect(listPanel.getByTestId('history-row').first()).toBeVisible();
  expect(historyRequests).toHaveLength(1);

  // Search matches rows beyond the loaded pages — server-side.
  const searchBox = listPanel.getByRole('textbox');
  await searchBox.fill('zebra');
  await expect
    .poll(() => historyRequests.length, { timeout: 5_000 })
    .toBe(2);
  expect(historyRequests[1]).toContain('search=zebra');

  // Exact filtered first page from the server (25 seeded matches).
  await expect(listPanel.getByTestId('history-row')).toHaveCount(PAGE_SIZE);

  // Load More stays explicit and bounded: one click → exactly one more request.
  await listPanel.getByRole('button', { name: /load more|تحميل المزيد/i }).click();
  await expect(listPanel.getByTestId('history-row')).toHaveCount(25);
  expect(historyRequests).toHaveLength(3);
  expect(historyRequests[2]).toContain('cursor=');

  // Cross-user isolation: user B's bait rows never appear.
  await expect(listPanel.getByText(/cross-user bait/)).toHaveCount(0);

  // Literal wildcard matching through the same server path.
  await searchBox.fill('100%_done');
  await expect(listPanel.getByTestId('history-row')).toHaveCount(4);
});

test('selection reconciles when the filter excludes the selected row', async ({ page }) => {
  test.skip(
    !LIVE_USERNAME || !LIVE_PASSWORD,
    'CHUNK-20 disposable live credentials are required.'
  );
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page);
  await page.goto('/history');
  const listPanel = page.getByTestId('history-list-panel');
  const detailPanel = page.getByTestId('history-detail-panel');

  await listPanel.getByTestId('history-row').first().click();
  await expect(detailPanel.getByTestId('history-detail')).toBeVisible();

  await listPanel.getByRole('textbox').fill('filler question number 7');
  await expect(detailPanel.getByText(/select an item/i)).toBeVisible({ timeout: 5_000 });
});
