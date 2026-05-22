import { test, expect, type Page } from '@playwright/test';
import en from '../../src/locales/en.json' assert { type: 'json' };
import { mockSubmitEvaluatorRejected, mockSubmitTimeout, mockHistoryEmpty } from './helpers/mock-backend';

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

function flattenKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) => {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      return flattenKeys(v as Record<string, unknown>, key);
    }
    return [key];
  });
}

const allKeys = flattenKeys(en);
const keySet = new Set(allKeys);

/**
 * Scan page text for tokens that match an i18n key exactly.
 * A "leak" is a DOM text node that contains a raw key string
 * (e.g. "error.unauthorized") instead of its translated value.
 */
async function assertNoMissingKeys(page: Page, url: string) {
  await page.goto(url);
  await page.waitForLoadState('networkidle');
  const bodyText = await page.locator('body').textContent() ?? '';
  const tokens = bodyText.split(/[\s\p{P}]+/u);
  const leaks: string[] = [];
  for (const token of tokens) {
    const trimmed = token.trim();
    if (!trimmed) continue;
    if (/^[a-z][a-zA-Z0-9_]*(?:\.[a-z][a-zA-Z0-9_]*)+$/.test(trimmed) && keySet.has(trimmed)) {
      leaks.push(trimmed);
    }
  }
  if (leaks.length > 0) {
    throw new Error(`Missing i18n key leaks: ${leaks.join(', ')}`);
  }
}

test.describe('T-185: no missing-key placeholders', () => {
  test('/sign-in has no raw i18n key strings', async ({ page }) => {
    await assertNoMissingKeys(page, '/sign-in');
  });

  test('/ (ask page) has no raw i18n key strings', async ({ page }) => {
    await signIn(page);
    await assertNoMissingKeys(page, '/');
  });

  test('/history has no raw i18n key strings', async ({ page }) => {
    await signIn(page);
    await assertNoMissingKeys(page, '/history');
  });
});

test.describe('T-186: no physical-direction CSS regression', () => {
  test('RTL mirrors layout on /sign-in', async ({ page }) => {
    await page.goto('/sign-in');
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible();

    const getStyles = () =>
      page.evaluate(() => {
        const heading = document.querySelector('h1');
        const input = document.querySelector('input');
        const btn = document.querySelector('button');
        const targets = [heading, input, btn].filter(Boolean) as HTMLElement[];
        return targets.map((el) => ({
          tag: el.tagName,
          textAlign: getComputedStyle(el).textAlign,
          marginLeft: getComputedStyle(el).marginLeft,
          marginRight: getComputedStyle(el).marginRight,
        }));
      });

    await getStyles();
    await page.evaluate(() => { document.documentElement.dir = 'rtl'; });
    const rtlStyles = await getStyles();

    // At least one element should have text-align flip to 'right' in RTL
    const hasFlippedTextAlign = rtlStyles.some(
      (s) => s.textAlign === 'right' || s.textAlign === 'end'
    );
    expect(hasFlippedTextAlign).toBe(true);

    // Zero elements should have non-zero margin-left paired with zero margin-right
    // (this would indicate physical-direction CSS instead of logical properties)
    const physicalDirectionLeak = rtlStyles.some((s) => {
      const ml = parseFloat(s.marginLeft);
      const mr = parseFloat(s.marginRight);
      return ml > 0 && mr === 0;
    });
    expect(physicalDirectionLeak).toBe(false);

    await page.evaluate(() => { document.documentElement.dir = 'ltr'; });
  });

  test('RTL mirrors layout on /history', async ({ page }) => {
    await signIn(page);
    await page.goto('/history');
    await expect(page.getByRole('heading', { name: /history/i })).toBeVisible();

    const getStyles = () =>
      page.evaluate(() => {
        const heading = document.querySelector('h1');
        const filterInput = document.querySelector('input[type="text"]');
        const items = Array.from(document.querySelectorAll('li, tr'));
        const targets = [heading, filterInput, ...items.slice(0, 3)].filter(
          Boolean
        ) as HTMLElement[];
        return targets.map((el) => ({
          tag: el.tagName,
          textAlign: getComputedStyle(el).textAlign,
          marginLeft: getComputedStyle(el).marginLeft,
          marginRight: getComputedStyle(el).marginRight,
        }));
      });

    await getStyles();
    await page.evaluate(() => { document.documentElement.dir = 'rtl'; });
    const rtlStyles = await getStyles();

    const hasFlippedTextAlign = rtlStyles.some(
      (s) => s.textAlign === 'right' || s.textAlign === 'end'
    );
    expect(hasFlippedTextAlign).toBe(true);

    const physicalDirectionLeak = rtlStyles.some((s) => {
      const ml = parseFloat(s.marginLeft);
      const mr = parseFloat(s.marginRight);
      return ml > 0 && mr === 0;
    });
    expect(physicalDirectionLeak).toBe(false);

    await page.evaluate(() => { document.documentElement.dir = 'ltr'; });
  });
});

test.describe('F-010: error/modal/empty states have no key leaks', () => {
  test('evaluator-rejected /query/submit shows no raw keys', async ({ page }) => {
    await signIn(page);
    await mockSubmitEvaluatorRejected(page);
    await page.goto('/');
    await page.fill('textarea', 'unsafe query');
    await page.getByRole('button', { name: /ask/i }).click();
    await page.waitForSelector('[role="alert"]', { timeout: 5_000 });
    await assertNoMissingKeys(page, '/');
  });

  test('timeout /query/submit shows no raw keys', async ({ page }) => {
    await signIn(page);
    await mockSubmitTimeout(page);
    await page.goto('/');
    await page.fill('textarea', 'slow query');
    await page.getByRole('button', { name: /ask/i }).click();
    await page.waitForSelector('[role="alert"]', { timeout: 5_000 });
    await assertNoMissingKeys(page, '/');
  });

  test('empty /history shows no raw keys', async ({ page }) => {
    await signIn(page);
    await mockHistoryEmpty(page);
    await page.goto('/history');
    await page.waitForLoadState('networkidle');
    await assertNoMissingKeys(page, '/history');
  });
});

test.describe('F-004 regression: 2-segment key leak detection', () => {
  test('injected 2-segment raw key is flagged by audit', async ({ page }) => {
    await page.goto('/sign-in');
    await page.waitForLoadState('networkidle');

    // Inject a known 2-segment key that exists in en.json
    await page.evaluate(() => {
      const div = document.createElement('div');
      div.id = 'leak-injection';
      div.textContent = 'error.unauthorized';
      document.body.appendChild(div);
    });

    let leaked = false;
    try {
      await assertNoMissingKeys(page, '/sign-in');
    } catch (e: unknown) {
      if (e instanceof Error && e.message.includes('error.unauthorized')) {
        leaked = true;
      }
    }
    expect(leaked).toBe(true);

    // Clean up injection and verify audit passes
    await page.evaluate(() => {
      const div = document.getElementById('leak-injection');
      if (div) div.remove();
    });
    await assertNoMissingKeys(page, '/sign-in');
  });
});
