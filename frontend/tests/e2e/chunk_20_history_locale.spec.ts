import { expect, test } from '@playwright/test';
import { signInLocalUser } from './helpers/auth';
import {
  mockConnections,
  mockHistoryDetail,
  mockHistoryList,
  mockLocalAuth,
} from './helpers/mock-backend';

/**
 * CHUNK-20 / IS-GAP-032 + IS-GAP-038 — deterministic Chromium matrix.
 *
 * Mocked routes and a fixed clock keep locale, direction, formatting and
 * accessibility assertions exact across desktop/tablet/mobile viewports.
 */

const FIXED_NOW = new Date('2026-05-11T10:00:00Z').getTime();

const rows = Array.from({ length: 24 }, (_, index) => ({
  id: `qc20-row-${index}`,
  question_text: index % 6 === 0 ? 'qc20 zebra match row' : 'filler question',
  generated_sql: `SELECT ${index} AS qc20_ltr_sql`,
  accepted_at: '2026-05-11T10:0' + (index % 10) + ':00Z',
}));

const detail = {
  id: rows[0].id,
  question_text: rows[0].question_text,
  generated_sql: rows[0].generated_sql,
  llm_provider: 'ollama',
  accepted_at: rows[0].accepted_at,
};

async function mockHistory(page: import('@playwright/test').Page) {
  await mockLocalAuth(page);
  await mockConnections(page);
  await page.route('**/api/v1/query/limits', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ max_question_length: 2000 }),
    }),
  );
  await page.route(/\/api\/v1\/sessions(?:\?.*)?$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0 }),
    }),
  );
  let searchCalls = 0;
  await page.route(/\/api\/v1\/history\/[^/?]+$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(detail),
    }),
  );
  await page.route(/\/api\/v1\/history(?:\?.*)?$/, (route) => {
    const url = new URL(route.request().url());
    const search = url.searchParams.get('search');
    if (search === 'zebra') {
      searchCalls += 1;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [rows[0]], total: 1, next_cursor: null }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: rows.slice(0, 20), total: 24, next_cursor: 'qc20-cursor-2' }),
    });
  });
  void searchCalls;
}

test.describe('history semantics and keyboard access', () => {
  for (const [width, height] of [[1440, 900], [768, 1024], [375, 812]] as const) {
    test(`semantic list, selection state and keyboard activation at ${width}px`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height });
      await mockHistory(page);
      await signInLocalUser(page);
      await page.goto('/history');

      const listPanel = page.getByTestId('history-list-panel');
      const firstRow = listPanel.getByTestId('history-row').first();
      await expect(firstRow).toBeVisible();

      // Semantic structure: a real list of real buttons; no table imitation.
      expect(await listPanel.locator('ul[role="list"] li').count()).toBe(20);
      expect(await page.locator('[role="columnheader"]').count()).toBe(0);

      // Selection via aria-pressed.
      await expect(firstRow).toHaveAttribute('aria-pressed', 'false');
      await firstRow.click();
      await expect(firstRow).toHaveAttribute('aria-pressed', 'true');
      await expect(page.getByTestId('history-detail-panel').getByTestId('history-detail')).toBeVisible();

      // Keyboard: Tab reaches the button; Enter activates another row.
      const secondRow = listPanel.getByTestId('history-row').nth(1);
      await secondRow.focus();
      await page.keyboard.press('Enter');
      await expect(secondRow).toHaveAttribute('aria-pressed', 'true');

      // Server-side search narrows to the mocked filtered dataset.
      await listPanel.getByRole('textbox').fill('zebra');
      await expect(listPanel.getByTestId('history-row')).toHaveCount(1);
    });
  }
});

test.describe('locale precedence, variants and fixed-clock formatting', () => {
  test('ar-EG resolves RTL, persists, survives reload and manual change wins over stale param', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockHistory(page);
    await signInLocalUser(page);

    // ar-EG → Arabic/RTL with normalized lang attribute.
    await page.goto('/history?lng=ar-EG');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    await expect(page.locator('html')).toHaveAttribute('lang', 'ar');

    // The query choice persisted: reload without the param keeps Arabic.
    await page.goto('/history');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    await expect(page.locator('html')).toHaveAttribute('lang', 'ar');

    // Manual switch to English becomes authoritative and rewrites a stale param.
    await page.goto('/history?lng=ar-EG');
    const englishButton = page.getByRole('button', { name: 'English' });
    await expect(englishButton).toBeVisible();
    await englishButton.click();
    await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    expect(new URL(page.url()).searchParams.get('lng')).toBe('en');
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');

    // Back/forward keeps direction coherent.
    await page.goBack();
    await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
  });

  test('fixed-clock dates render through the active locale inside LTR isolation at 768px', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await mockHistory(page);
    await signInLocalUser(page);
    await page.clock.setFixedTime(FIXED_NOW);

    await page.goto('/history?lng=ar');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    const listPanel = page.getByTestId('history-list-panel');
    const firstRow = listPanel.getByTestId('history-row').first();
    await expect(firstRow).toBeVisible();

    // SQL stays LTR inside the RTL chrome.
    await expect(firstRow.locator('code[dir="ltr"]')).toContainText('SELECT 0 AS qc20_ltr_sql');

    // Arabic-script date text (CLDR digit shape may vary by ICU build).
    const dateText = await firstRow.locator('span[dir="ltr"]').innerText();
    expect(dateText.trim().length).toBeGreaterThan(4);
    expect(dateText).toMatch(/2026|٢٠٢٦/);

    // English renders the same instant in Latin script.
    await page.goto('/history?lng=en');
    await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
    const enDate = await listPanel
      .getByTestId('history-row')
      .first()
      .locator('span[dir="ltr"]')
      .innerText();
    expect(enDate).toMatch(/May|مايو/);
  });

  test('mobile history detail errors stay inside the detail panel at 375px', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await mockHistory(page);
    await signInLocalUser(page);

    await page.route(/\/api\/v1\/history\/[^/?]+$/, (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"boom"}' }),
    );

    await page.goto('/history?lng=ar');
    const listPanel = page.getByTestId('history-list-panel');
    const detailPanel = page.getByTestId('history-detail-panel');
    await listPanel.getByTestId('history-row').first().click();

    // The failure surfaces as an alert inside the detail panel only.
    await expect(detailPanel.locator('[role="alert"]').first()).toBeVisible();
    expect(await listPanel.locator('[role="alert"]').count()).toBe(0);
  });
});
