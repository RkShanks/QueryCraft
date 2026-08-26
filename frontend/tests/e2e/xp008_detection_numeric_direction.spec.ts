import { expect, test, type Locator, type Page } from '@playwright/test';
import ar from '../../src/locales/ar.json' with { type: 'json' };
import en from '../../src/locales/en.json' with { type: 'json' };
import { signInLocalUser } from './helpers/auth';
import { mockConnections, mockLocalAuth, mockQueryLimits, mockSessionsList } from './helpers/mock-backend';

const localeMessages = { en, ar } as const;
const thresholdKeys = [
  'detection.block_threshold',
  'detection.flag_threshold',
] as const;

function message(locale: 'en' | 'ar', key: (typeof thresholdKeys)[number]) {
  return (localeMessages[locale] as Record<string, string>)[key];
}

async function mockDetectionPage(page: Page) {
  await mockLocalAuth(page);
  await mockConnections(page);
  await mockSessionsList(page);
  await mockQueryLimits(page);
  await page.route('**/api/v1/admin/detection/config', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        block_confidence: 0.8,
        flag_confidence: 0.5,
        updated_at: '2026-07-31T00:00:00Z',
      }),
    })
  );
}

async function focusWithTab(page: Page, target: Locator) {
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  for (let tabCount = 0; tabCount < 80; tabCount += 1) {
    await page.keyboard.press('Tab');
    if (await target.evaluate((element) => element === document.activeElement)) return;
  }
  throw new Error(`Tab navigation did not reach ${await target.getAttribute('aria-label')}`);
}

async function expectVisibleKeyboardFocus(control: Locator) {
  await expect
    .poll(() =>
      control.evaluate((element) => {
        const style = getComputedStyle(element);
        return style.boxShadow !== 'none' || style.outlineStyle !== 'none';
      })
    )
    .toBe(true);
}

async function expectNoPageOverflow(page: Page) {
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth
      )
    )
    .toBeLessThanOrEqual(0);
}

// XP-008 regression (2026-07-31): detection numbers inherited RTL from the Arabic shell.
for (const viewport of [
  { width: 375, height: 812 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
]) {
  for (const locale of ['en', 'ar'] as const) {
    test(`keeps ${locale} detection thresholds LTR at ${viewport.width}px`, async ({
      page,
    }) => {
      const failedResponses: string[] = [];
      page.on('response', (response) => {
        if (response.status() >= 500) {
          failedResponses.push(`${response.status()} ${new URL(response.url()).pathname}`);
        }
      });
      await page.setViewportSize(viewport);
      await mockDetectionPage(page);
      await signInLocalUser(page);
      await page.goto(`/admin/detection?lng=${locale}`);

      await expect(page.locator('html')).toHaveAttribute(
        'dir',
        locale === 'ar' ? 'rtl' : 'ltr'
      );

      for (const key of thresholdKeys) {
        const control = page.getByRole('spinbutton', { name: message(locale, key) });
        await expect(control).toHaveAttribute('dir', 'ltr');
        await expect(control).toHaveCSS('direction', 'ltr');
        const previousValue = Number(await control.inputValue());
        await focusWithTab(page, control);
        await expectVisibleKeyboardFocus(control);
        await page.keyboard.press('ArrowUp');
        expect(Number(await control.inputValue())).toBeGreaterThan(previousValue);
      }

      await expectNoPageOverflow(page);
      expect(failedResponses).toEqual([]);
    });
  }
}
