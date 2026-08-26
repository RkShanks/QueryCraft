import { expect, test, type Locator, type Page } from '@playwright/test';
import ar from '../../src/locales/ar.json' with { type: 'json' };
import en from '../../src/locales/en.json' with { type: 'json' };
import { signInLocalUser } from './helpers/auth';
import { mockConnections, mockLocalAuth, mockQueryLimits, mockSessionsList } from './helpers/mock-backend';

const localeMessages = { en, ar } as const;
const numericSettingKeys = [
  'admin.settings.contextCap',
  'admin.settings.maxRegenerateAttempts',
] as const;

function message(locale: 'en' | 'ar', key: (typeof numericSettingKeys)[number]) {
  return (localeMessages[locale] as Record<string, string>)[key];
}

async function mockSettingsPage(page: Page) {
  await mockLocalAuth(page);
  await mockConnections(page);
  await mockSessionsList(page);
  await mockQueryLimits(page);
  await page.route('**/api/v1/admin/settings', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ llm_context_cap: 3, max_regenerate_attempts: 3 }),
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
  throw new Error(`Tab navigation did not reach ${await target.getAttribute('id')}`);
}

async function expectVisibleKeyboardFocus(control: Locator, unfocusedBorderColor: string) {
  await expect
    .poll(() =>
      control.evaluate((element) => {
        const style = getComputedStyle(element);
        return {
          borderColor: style.borderColor,
          boxShadow: style.boxShadow,
          outlineStyle: style.outlineStyle,
        };
      })
    )
    .not.toEqual({
      borderColor: unfocusedBorderColor,
      boxShadow: 'none',
      outlineStyle: 'none',
    });
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

// XP-008 regression (2026-07-31): settings numbers inherited RTL from the Arabic shell.
for (const viewport of [
  { width: 375, height: 812 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
]) {
  for (const locale of ['en', 'ar'] as const) {
    test(`keeps ${locale} numeric settings LTR at ${viewport.width}px`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await mockSettingsPage(page);
      await signInLocalUser(page);
      await page.goto(`/settings?lng=${locale}`);

      const rootDirection = locale === 'ar' ? 'rtl' : 'ltr';
      await expect(page.locator('html')).toHaveAttribute('dir', rootDirection);

      for (const key of numericSettingKeys) {
        const control = page.getByLabel(message(locale, key));
        await expect(control).toHaveAttribute('dir', 'ltr');
        await expect(control).toHaveCSS('direction', 'ltr');
        const unfocusedBorderColor = await control.evaluate(
          (element) => getComputedStyle(element).borderColor
        );
        await focusWithTab(page, control);
        await expectVisibleKeyboardFocus(control, unfocusedBorderColor);
        await page.keyboard.press('ArrowUp');
        await expect(control).toHaveValue('4');
      }
      await expectNoPageOverflow(page);

      await page.reload();
      await expect(page.locator('html')).toHaveAttribute('dir', rootDirection);
      for (const key of numericSettingKeys) {
        const control = page.getByLabel(message(locale, key));
        await expect(control).toHaveAttribute('dir', 'ltr');
        await expect(control).toHaveCSS('direction', 'ltr');
      }
      await expectNoPageOverflow(page);
    });
  }
}
