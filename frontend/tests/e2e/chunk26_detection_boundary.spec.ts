import { expect, test, type Page, type Route } from '@playwright/test';
import ar from '../../src/locales/ar.json' with { type: 'json' };
import en from '../../src/locales/en.json' with { type: 'json' };
import { signInLocalUser } from './helpers/auth';
import { mockConnections, mockLocalAuth } from './helpers/mock-backend';

const messages = { en, ar } as const;
type Locale = keyof typeof messages;

const VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 768, height: 1024 },
  { width: 375, height: 812 },
] as const;

const CLIENT_BLOCKED_VALUES = ['-0.5', '1.5', '1e999', '-1e999'] as const;

interface DetectionMockOptions {
  locale: Locale;
  onPut?: (request: Request) => void;
  putResponder?: (request: Request) => { status: number; body?: unknown };
}

async function mockDetectionPage(page: Page, options: DetectionMockOptions) {
  await mockLocalAuth(page);
  await mockConnections(page);
  await page.route(/\/api\/v1\/sessions(?:\?.*)$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0, next_cursor: null }),
    })
  );
  await page.route('**/api/v1/admin/detection/config', async (route: Route) => {
    const request = route.request();
    if (request.method() === 'PUT') {
      options.onPut?.(request);
      const responder = options.putResponder;
      const outcome = responder
        ? responder(request)
        : {
            status: 200,
            body: {
              ...JSON.parse(request.postData() ?? '{}'),
              updated_at: '2026-08-26T01:00:00Z',
            },
          };
      await route.fulfill({
        status: outcome.status,
        contentType: 'application/json',
        body: JSON.stringify(outcome.body),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        block_confidence: 0.8,
        flag_confidence: 0.5,
        updated_at: '2026-08-26T00:00:00Z',
      }),
    });
  });
}

async function openDetectionPage(page: Page, locale: Locale) {
  await signInLocalUser(page);
  await page.goto(`/admin/detection?lng=${locale}`);
  const block = page.getByRole('spinbutton', {
    name: messages[locale]['detection.block_threshold'],
  });
  const flag = page.getByRole('spinbutton', {
    name: messages[locale]['detection.flag_threshold'],
  });
  await expect(block).toBeVisible();
  return { block, flag };
}

function saveButton(page: Page, locale: Locale) {
  return page.getByRole('button', { name: messages[locale]['detection.save'] });
}

for (const viewport of VIEWPORTS) {
  test(`invalid threshold bypass values create zero mutations at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    let putCount = 0;
    await mockDetectionPage(page, { locale: 'en', onPut: () => void (putCount += 1) });
    const { block } = await openDetectionPage(page, 'en');

    for (const raw of CLIENT_BLOCKED_VALUES) {
      await block.fill(raw);
      await saveButton(page, 'en').click();
      expect(putCount, `value ${raw} must not mutate`).toBe(0);

      const nativeBlocked = await block.evaluate(
        (element) => !(element as HTMLInputElement).checkValidity()
      );
      if (!nativeBlocked) {
        await expect(page.getByRole('alert')).toContainText(
          messages.en['detection.validation_range']
        );
        await expect(block).toHaveAttribute('aria-invalid', 'true');
        const describedBy = await block.getAttribute('aria-describedby');
        expect(describedBy).toBeTruthy();
        await expect(page.locator(`#${describedBy}`)).toBeVisible();
      }
    }
  });

  test(`keyboard edit and Enter submit stay blocked for out-of-range input at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    let putCount = 0;
    await mockDetectionPage(page, { locale: 'en', onPut: () => void (putCount += 1) });
    const { block, flag } = await openDetectionPage(page, 'en');

    await block.fill('0.9');
    await flag.fill('0.95');
    await block.press('Enter');

    await expect(page.getByRole('alert')).toContainText(
      messages.en['detection.validation_error']
    );
    expect(putCount).toBe(0);
  });

  test(`reset restores authoritative thresholds without mutating at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    let putCount = 0;
    await mockDetectionPage(page, { locale: 'en', onPut: () => void (putCount += 1) });
    const { block } = await openDetectionPage(page, 'en');

    await block.fill('0.2');
    await page.getByRole('button', { name: messages.en['detection.reset'] }).click();

    await expect(block).toHaveValue(/0\.8/);
    expect(putCount).toBe(0);
  });
}

test('valid boundary thresholds save exactly once with the exact payload', async ({ page }) => {
  let putCount = 0;
  let payload: unknown = null;
  await mockDetectionPage(page, {
    locale: 'en',
    onPut: (request) => {
      putCount += 1;
      payload = JSON.parse(request.postData() ?? 'null');
    },
  });
  await page.setViewportSize(VIEWPORTS[0]);
  const { block, flag } = await openDetectionPage(page, 'en');

  await block.fill('1');
  await flag.fill('0');
  await saveButton(page, 'en').click();

  await expect(
    page.getByRole('status').filter({ hasText: 'Changes saved successfully' })
  ).toBeVisible();
  expect(putCount).toBe(1);
  expect(payload).toEqual({ block_confidence: 1, flag_confidence: 0 });
});

test('sanitized server rejection preserves edits and retry recovers', async ({ page }) => {
  let putCount = 0;
  let rejectedOnce = false;
  await mockDetectionPage(page, {
    locale: 'en',
    onPut: () => void (putCount += 1),
    putResponder: () => {
      if (!rejectedOnce) {
        rejectedOnce = true;
        return {
          status: 422,
          body: {
            detail: [
              {
                loc: ['body', 'block_confidence'],
                msg: 'Input should be less than or equal to 1',
                type: 'less_than_equal',
              },
            ],
          },
        };
      }
      return {
        status: 200,
        body: { block_confidence: 0.9, flag_confidence: 0.85, updated_at: '2026-08-26T01:00:00Z' },
      };
    },
  });
  await page.setViewportSize(VIEWPORTS[1]);
  const { block, flag } = await openDetectionPage(page, 'en');

  await block.fill('0.9');
  await flag.fill('0.85');
  await saveButton(page, 'en').click();

  const failureToast = page.getByRole('alert').filter({
    hasText: messages.en['detection.save_error'],
  });
  await expect(failureToast).toBeVisible();
  expect(await page.textContent('body')).not.toContain('less_than_equal');

  await expect(block).toHaveValue(/0\.9/);
  await expect(flag).toHaveValue(/0\.85/);

  await saveButton(page, 'en').click();
  await expect(
    page.getByRole('status').filter({ hasText: 'Changes saved successfully' })
  ).toBeVisible();
  expect(putCount).toBe(2);
});

test('arabic boundary rejection announces localized client errors at 375px', async ({ page }) => {
  let putCount = 0;
  await mockDetectionPage(page, { locale: 'ar', onPut: () => void (putCount += 1) });
  await page.setViewportSize(VIEWPORTS[2]);
  const { block, flag } = await openDetectionPage(page, 'ar');

  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');

  await block.fill('1.5');
  await saveButton(page, 'ar').click();
  const nativeBlocked = await block.evaluate(
    (element) => !(element as HTMLInputElement).checkValidity()
  );
  expect(nativeBlocked).toBe(true);
  expect(putCount).toBe(0);

  await block.fill('0.5');
  await flag.fill('0.6');
  await saveButton(page, 'ar').click();
  await expect(page.getByRole('alert')).toContainText(
    messages.ar['detection.validation_error']
  );
  expect(putCount).toBe(0);
  await expect(block).toHaveAttribute('aria-invalid', 'true');
  const describedBy = await block.getAttribute('aria-describedby');
  expect(describedBy).toBeTruthy();
  await expect(page.locator(`#${describedBy}`)).toContainText(
    messages.ar['detection.validation_error']
  );
});
