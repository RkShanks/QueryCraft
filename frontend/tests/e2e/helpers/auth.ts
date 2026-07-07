import { expect, type Page } from '@playwright/test';

const getLocalAdminUsername = () =>
  process.env.E2E_ADMIN_USERNAME ?? process.env.E2E_TEST_USERNAME ?? process.env.ADMIN_USERNAME ?? 'admin';

const getLocalAdminPassword = () =>
  process.env.E2E_ADMIN_PASSWORD ?? process.env.E2E_TEST_PASSWORD ?? process.env.ADMIN_PASSWORD ?? 'admin123';

type SignInLocalUserOptions = {
  username?: string;
  password?: string;
};

export async function signInLocalUser(page: Page, options: SignInLocalUserOptions = {}) {
  const username = options.username ?? getLocalAdminUsername();
  const password = options.password ?? getLocalAdminPassword();

  if (!password) {
    throw new Error('Local sign-in password is not configured for e2e.');
  }

  await page.goto('/');
  await expect(page).toHaveURL(/\/sign-in/, { timeout: 5_000 });

  const form = page.locator('form.sign-in-form');
  await expect(form).toBeVisible({ timeout: 5_000 });
  await form.getByLabel(/username/i).fill(username);
  await form.getByLabel(/password/i).fill(password);
  await form.getByRole('button', { name: /^sign in$/i }).click();

  await expect(page).toHaveURL(/\/(ask)?\/?$/);
}
