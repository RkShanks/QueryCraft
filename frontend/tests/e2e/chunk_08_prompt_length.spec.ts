import { expect, test, type Page, type Route } from '@playwright/test';

import { signInLocalUser } from './helpers/auth';
import { mockConnections, mockLocalAuth } from './helpers/mock-backend';

const CONFIGURED_LIMIT = 37;

test.use({ screenshot: 'off', trace: 'off', video: 'off' });

async function mockWorkspaceBoundary(page: Page, handleLimits: (route: Route) => Promise<void>) {
  await mockLocalAuth(page);
  await mockConnections(page);
  await page.route('**/api/v1/query/limits', handleLimits);
  await page.route(/\/api\/v1\/sessions(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0 }),
    });
  });
}

const browserCases = [
  { name: 'EN desktop', locale: 'en', direction: 'ltr', width: 1280, height: 800, codePoint: 'x' },
  { name: 'AR desktop', locale: 'ar', direction: 'rtl', width: 1280, height: 800, codePoint: 'س' },
  { name: 'EN 375px', locale: 'en', direction: 'ltr', width: 375, height: 812, codePoint: '😀' },
  { name: 'AR 375px', locale: 'ar', direction: 'rtl', width: 375, height: 812, codePoint: 'س' },
] as const;

test.describe('CHUNK-08 configured primary prompt length', () => {
  for (const browserCase of browserCases) {
    test(`${browserCase.name} blocks over-limit input and deduplicates the exact limit`, async ({
      page,
    }) => {
      let submitRequestCount = 0;
      await page.setViewportSize({ width: browserCase.width, height: browserCase.height });
      await mockWorkspaceBoundary(page, async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ max_question_length: CONFIGURED_LIMIT }),
        });
      });
      await page.route('**/api/v1/query/submit', async (route) => {
        submitRequestCount += 1;
        await new Promise((resolve) => setTimeout(resolve, 100));
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            kind: 'result',
            attempt_id: 'chunk-08-attempt',
            question: '',
            generated_sql: 'SELECT 1',
            columns: [],
            rows: [],
            row_count: 0,
            attempt_number: 1,
            is_last_auto_retry: false,
          }),
        });
      });

      await signInLocalUser(page);
      await page.goto(`/?lng=${browserCase.locale}`);
      await expect(page.locator('html')).toHaveAttribute('dir', browserCase.direction);

      const input = page.getByRole('textbox');
      await expect(input).toBeEnabled();
      const overLimitText = browserCase.codePoint.repeat(CONFIGURED_LIMIT + 1);
      await input.fill(overLimitText);
      await expect(page.getByTestId('prompt-character-count')).toHaveText(
        `${CONFIGURED_LIMIT + 1} / ${CONFIGURED_LIMIT}`
      );
      const error = page.getByRole('alert').filter({
        hasText:
          browserCase.locale === 'ar'
            ? `يجب ألا يتجاوز السؤال ${CONFIGURED_LIMIT} حرفاً.`
            : `Question must be at most ${CONFIGURED_LIMIT} characters.`,
      });
      await expect(error).toBeVisible();
      await expect(input).toHaveAttribute('aria-invalid', 'true');
      await expect(input).toHaveAttribute('aria-describedby', /prompt-length-error/);

      await input.press('Enter');
      await page.getByTestId('prompt-send').evaluate((button: HTMLButtonElement) => button.click());
      expect(submitRequestCount).toBe(0);
      expect(await input.evaluate((element: HTMLTextAreaElement) => Array.from(element.value).length))
        .toBe(CONFIGURED_LIMIT + 1);

      await input.fill(browserCase.codePoint.repeat(CONFIGURED_LIMIT));
      await expect(page.getByTestId('prompt-character-count')).toHaveText(
        `${CONFIGURED_LIMIT} / ${CONFIGURED_LIMIT}`
      );
      await page.getByTestId('prompt-send').dblclick();
      await expect.poll(() => submitRequestCount).toBe(1);

      const promptBox = await page.getByTestId('prompt-input').boundingBox();
      expect(promptBox).not.toBeNull();
      expect(promptBox?.x).toBeGreaterThanOrEqual(0);
      expect((promptBox?.x ?? 0) + (promptBox?.width ?? 0)).toBeLessThanOrEqual(browserCase.width);
    });
  }

  test('loading and sanitized failure states stay closed until explicit retry succeeds', async ({
    page,
  }) => {
    let limitsRequestCount = 0;
    let submitRequestCount = 0;
    await mockWorkspaceBoundary(page, async (route) => {
      limitsRequestCount += 1;
      if (limitsRequestCount <= 2) {
        await route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'service_unavailable', message_key: 'error.service_unavailable' }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ max_question_length: CONFIGURED_LIMIT }),
      });
    });
    await page.route('**/api/v1/query/submit', async (route) => {
      submitRequestCount += 1;
      await route.abort();
    });

    await signInLocalUser(page);
    const input = page.getByRole('textbox');
    await expect(input).toBeDisabled();
    await expect(page.getByText('Unable to load the question limit.')).toBeVisible({ timeout: 5_000 });
    expect(submitRequestCount).toBe(0);

    await page.getByRole('button', { name: 'Retry' }).click();
    await expect(input).toBeEnabled();
    await expect(page.getByTestId('prompt-character-count')).toHaveText(`0 / ${CONFIGURED_LIMIT}`);
    expect(limitsRequestCount).toBe(3);
    expect(submitRequestCount).toBe(0);
  });
});
