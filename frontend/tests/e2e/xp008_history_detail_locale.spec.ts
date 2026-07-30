import { expect, test, type Page } from '@playwright/test';
import { signInLocalUser } from './helpers/auth';
import {
  mockConnections,
  mockHistoryDetail,
  mockHistoryList,
  mockLocalAuth,
} from './helpers/mock-backend';

const historyItem = {
  id: 'locale-history-detail',
  question_text: 'Customer count',
  generated_sql: 'SELECT COUNT(*) FROM customer',
  accepted_at: '2026-07-31T00:00:00Z',
};

async function mockHistoryPage(page: Page) {
  await mockLocalAuth(page);
  await mockConnections(page);
  await page.route(/\/api\/v1\/sessions(?:\?.*)?$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0 }),
    })
  );
  await mockHistoryList(page, {
    items: [historyItem],
    total: 1,
    next_cursor: null,
  });
  await mockHistoryDetail(page, historyItem);
}

// XP-008 regression (2026-07-31): the history action leaked a raw key in both locales.
for (const { locale, direction, actionLabel } of [
  { locale: 'en', direction: 'ltr', actionLabel: 'Load in Workspace' },
  { locale: 'ar', direction: 'rtl', actionLabel: 'تحميل في مساحة العمل' },
] as const) {
  test(`localizes the ${locale} history workspace action without key warnings`, async ({
    page,
  }) => {
    const missingKeyWarnings: string[] = [];
    page.on('console', (message) => {
      if (
        message.type() === 'warning' &&
        message.text().includes('history.detail.loadInWorkspace')
      ) {
        missingKeyWarnings.push(message.text());
      }
    });

    await mockHistoryPage(page);
    await signInLocalUser(page);
    await page.goto(`/history?lng=${locale}`);
    await page.getByText(historyItem.question_text).click();

    const detail = page.getByTestId('history-detail');
    await expect(page.locator('html')).toHaveAttribute('dir', direction);
    await expect(detail.getByRole('button', { name: actionLabel })).toBeVisible();
    await expect(detail).not.toContainText('history.detail.loadInWorkspace');
    if (locale === 'ar') {
      await expect(detail).not.toContainText(/Load in (?:Workspace|Chat)/);
    }
    expect(missingKeyWarnings).toEqual([]);
  });
}
