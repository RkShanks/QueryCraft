import { expect, test } from '@playwright/test';

const SECRET = 'chunk19-wrong-password-canary';

test.use({ screenshot: 'off', trace: 'off', video: 'off' });

test.describe('CHUNK-19 live sign-in round trip', () => {
  test('rejected credentials stay safe and valid credentials reach the workspace through the real API', async ({
    page,
  }) => {
    const username = process.env.CHUNK19_LIVE_USERNAME;
    const password = process.env.CHUNK19_LIVE_PASSWORD;

    test.skip(
      !username || !password,
      'CHUNK-19 disposable live credentials are required.'
    );

    const browserOutput: string[] = [];
    page.on('console', (message) => browserOutput.push(message.text()));
    page.on('pageerror', (error) => browserOutput.push(error.message));

    await page.goto('/sign-in?lng=en');
    const form = page.locator('form.sign-in-form');
    await expect(form).toBeVisible({ timeout: 10_000 });

    // Client boundary still guards an empty submission without any request.
    await form.getByRole('button', { name: /sign in/i }).click();
    await expect(page.getByRole('alert')).toContainText('Username cannot be empty.');

    // Server rejection against the real API keeps both secrets out of the UI.
    await form.getByLabel(/username/i).fill(username!);
    await form.getByLabel(/password/i).fill(SECRET);
    await form.getByRole('button', { name: /sign in/i }).click();
    await page.waitForResponse(
      (response) =>
        response.url().includes('/auth/sign-in') && response.status() === 401
    );
    for (const message of browserOutput) {
      expect(message).not.toContain(SECRET);
      expect(message).not.toContain(password!);
    }
    await expect(page.locator('body')).not.toContainText(SECRET);

    // The real disposable administrator round trip reaches the workspace.
    await form.getByLabel(/username/i).fill(username!);
    await form.getByLabel(/password/i).fill(password!);
    await form.getByRole('button', { name: /sign in/i }).click();
    await expect(page).not.toHaveURL(/sign-in/, { timeout: 15_000 });
    for (const message of browserOutput) {
      expect(message).not.toContain(password!);
    }
  });
});
