import { expect, test, type Page } from '@playwright/test';

import type { QueryResult } from '../../src/api/generated/types.gen';
import { signInLocalUser } from './helpers/auth';
import { mockConnections, mockLocalAuth } from './helpers/mock-backend';

const SESSION_ID = '550e8400-e29b-41d4-a716-446655440121';
const ATTEMPT_ID = '550e8400-e29b-41d4-a716-446655440122';
const SAVED_ID = '550e8400-e29b-41d4-a716-446655440123';
const RAW_CANARY = 'RAW_BACKEND_RECOVERY_CANARY';

test.use({ screenshot: 'off', trace: 'off', video: 'off' });

async function mockWorkspace(page: Page) {
  await mockLocalAuth(page);
  await mockConnections(page);
  await page.route('**/api/v1/query/limits', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ max_question_length: 2000 }),
    })
  );
  await page.route(/\/api\/v1\/sessions(?:\?.*)?$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0, next_cursor: null }),
    })
  );
}

async function openWorkspace(page: Page, locale: 'en' | 'ar') {
  await signInLocalUser(page);
  await page.goto(`/?lng=${locale}`);
  await expect(page.getByRole('textbox')).toBeEnabled();
}

async function submit(page: Page, question: string) {
  const input = page.getByRole('textbox');
  await input.fill(question);
  await input.press('Enter');
}

function result(rows: QueryResult['rows'], overrides: Partial<QueryResult> = {}): QueryResult {
  return {
    kind: 'result',
    attempt_id: ATTEMPT_ID,
    session_id: SESSION_ID,
    question: 'Bounded result question',
    generated_sql: 'SELECT bounded_value FROM synthetic_rows',
    columns: [{ name: 'bounded_value', type: 'integer', masked: true }],
    rows,
    row_count: rows.length,
    attempt_number: 1,
    is_last_auto_retry: false,
    accepted_query_id: SAVED_ID,
    ...overrides,
  };
}

async function expectInsideViewport(page: Page, selector: string) {
  const box = await page.locator(selector).boundingBox();
  expect(box).not.toBeNull();
  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();
  expect(box?.x).toBeGreaterThanOrEqual(0);
  expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(viewport?.width ?? 0);
}

test.describe('CHUNK-18 workspace result and recovery behavior', () => {
  test('1440px renders every returned row once while keeping each page at 50 rows', async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockWorkspace(page);
    const rows = Array.from({ length: 101 }, (_, index) => [index + 1]);
    await page.route('**/api/v1/query/submit', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(result(rows)),
      })
    );
    await openWorkspace(page, 'en');
    await submit(page, 'Show the bounded synthetic rows');

    const table = page.getByRole('table', { name: 'Results' });
    await expect(table).toBeVisible();
    await expect(page.getByText('Masked')).toBeVisible();
    const observed: string[] = [];
    for (let pageNumber = 1; pageNumber <= 3; pageNumber += 1) {
      const bodyRows = table.locator('tbody tr');
      expect(await bodyRows.count()).toBeLessThanOrEqual(50);
      observed.push(...(await bodyRows.locator('td').allTextContents()));
      if (pageNumber < 3) {
        await page.getByRole('button', { name: 'Next page' }).click();
      }
    }
    expect(observed).toEqual(rows.map(([value]) => String(value)));
    expect(new Set(observed).size).toBe(101);
    await expect(page.getByRole('status')).toContainText('Page 3 of 3');
    await expectInsideViewport(page, '[data-testid="result-table"]');
    await page.screenshot({ path: testInfo.outputPath('pagination-1440.png'), fullPage: true });
  });

  test('768px preserves the result through regenerate and delete failures with safe retries', async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 768, height: 900 });
    await mockWorkspace(page);
    await page.route('**/api/v1/query/submit', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(result([[7]])),
      })
    );

    let regenerateRequests = 0;
    await page.route('**/api/v1/query/regenerate', async (route) => {
      regenerateRequests += 1;
      if (regenerateRequests === 1) {
        await new Promise((resolve) => setTimeout(resolve, 150));
        await route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'service_unavailable',
            message_key: 'error.service_unavailable',
            debug: RAW_CANARY,
          }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          result([[8]], {
            attempt_id: '550e8400-e29b-41d4-a716-446655440124',
            accepted_query_id: '550e8400-e29b-41d4-a716-446655440125',
            generated_sql: 'SELECT 8 AS recovered_value',
            columns: [{ name: 'recovered_value', type: 'integer' }],
          })
        ),
      });
    });

    let deleteRequests = 0;
    await page.route('**/api/v1/history/*', async (route) => {
      if (route.request().method() !== 'DELETE') {
        await route.fallback();
        return;
      }
      deleteRequests += 1;
      if (deleteRequests === 1) {
        await route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'service_unavailable',
            message_key: 'error.service_unavailable',
            debug: RAW_CANARY,
          }),
        });
        return;
      }
      await route.fulfill({ status: 204 });
    });

    await openWorkspace(page, 'en');
    await submit(page, 'Recover this result');
    await expect(page.getByRole('cell', { name: '7' })).toBeVisible();
    const regenerate = page.getByRole('button', { name: 'Regenerate' });
    await regenerate.click();
    await expect(regenerate).toBeDisabled();
    await expect(page.getByRole('status')).toContainText('Regenerating the original attempt');
    await expect(page.getByRole('cell', { name: '7' })).toBeVisible();

    const regenerateAlert = page.getByRole('alert', {
      name: 'Regeneration failed. The previous result is still available.',
    });
    await expect(regenerateAlert).toBeVisible();
    await regenerateAlert.getByRole('button', { name: 'Retry' }).click();
    await expect(page.getByRole('cell', { name: '8' })).toBeVisible();
    expect(regenerateRequests).toBe(2);

    await page.getByRole('button', { name: 'Delete' }).click();
    const deleteAlert = page.getByRole('alert', {
      name: 'Delete failed. The result was restored.',
    });
    await expect(deleteAlert).toBeVisible();
    await expect(page.getByRole('cell', { name: '8' })).toBeVisible();
    await expect(page.locator('body')).not.toContainText(RAW_CANARY);
    await expectInsideViewport(page, '[data-testid="assistant-response-card"]');
    await page.screenshot({ path: testInfo.outputPath('recovery-768.png'), fullPage: true });

    await deleteAlert.getByRole('button', { name: 'Retry' }).click();
    await expect(page.getByTestId('assistant-response-card')).toHaveCount(0);
    expect(deleteRequests).toBe(2);
  });

  test('375px Arabic renders zero rows as success and retries a timeout with localized controls', async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await mockWorkspace(page);
    let submitRequests = 0;
    await page.route('**/api/v1/query/submit', async (route) => {
      submitRequests += 1;
      if (submitRequests === 1) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(result([])),
        });
        return;
      }
      if (submitRequests === 2) {
        await route.fulfill({
          status: 504,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'timeout',
            message_key: 'error.timeout',
            debug: RAW_CANARY,
          }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          result([[3]], {
            attempt_id: '550e8400-e29b-41d4-a716-446655440126',
            accepted_query_id: undefined,
          })
        ),
      });
    });

    await openWorkspace(page, 'ar');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    await submit(page, 'نتيجة فارغة');
    const table = page.getByRole('table', { name: 'النتائج' });
    await expect(table).toBeVisible();
    await expect(table.getByRole('cell', { name: 'لم يُعثر على نتائج لاستعلامك' })).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'صفحات النتائج' })).toHaveCount(0);

    await submit(page, 'أعد محاولة المهلة');
    const retry = page.getByRole('button', { name: 'إعادة المحاولة' });
    await expect(retry).toBeVisible();
    await retry.focus();
    await retry.click();
    await expect(page.getByRole('cell', { name: '3' })).toBeVisible();
    expect(submitRequests).toBe(3);
    await expect(page.locator('body')).not.toContainText(RAW_CANARY);
    await expectInsideViewport(page, '[data-testid="assistant-response-card"]');
    await page.screenshot({ path: testInfo.outputPath('zero-retry-ar-375.png'), fullPage: true });
  });
});
