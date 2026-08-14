import { expect, test } from '@playwright/test';

test('real API returns a valid public SSO-provider response', async ({ page }, testInfo) => {
  const providersResponse = page.waitForResponse(
    (response) =>
      response.url().includes('/api/v1/auth/sso/providers') && response.request().method() === 'GET'
  );

  await page.goto('/sign-in');
  const response = await providersResponse;
  expect(response.status()).toBe(200);
  expect(response.headers()['content-type']).toContain('application/json');
  const body = (await response.json()) as { providers?: unknown };
  expect(Array.isArray(body.providers)).toBe(true);
  await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible();
  await expect(page.getByText(/invalid response/i)).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('live-sso-providers.png'), fullPage: true });
});
