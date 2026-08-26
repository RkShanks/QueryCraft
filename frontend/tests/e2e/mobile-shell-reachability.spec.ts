import { expect, test, type Page } from '@playwright/test';
import { mockConnections, mockLocalAuth, mockQueryLimits, mockSessionsList } from './helpers/mock-backend';
import { signInLocalUser } from './helpers/auth';

async function mockShellData(page: Page) {
  await mockLocalAuth(page);
  await mockConnections(page);
  await mockSessionsList(page);
  await mockQueryLimits(page);
}

async function expectSidebarBesideWorkspace(page: Page) {
  const sidebar = await page.getByTestId('app-shell-sidebar').boundingBox();
  const workspace = await page.getByTestId('app-shell-workspace').boundingBox();
  expect(sidebar).not.toBeNull();
  expect(workspace).not.toBeNull();
  if (!sidebar || !workspace) return;

  const separated =
    sidebar.x + sidebar.width <= workspace.x + 1 ||
    workspace.x + workspace.width <= sidebar.x + 1;
  expect(separated).toBe(true);
}

test.describe('mobile app shell reachability', () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test('keeps the sidebar from intercepting workspace controls in LTR and RTL', async ({ page }) => {
    await mockShellData(page);
    await signInLocalUser(page);

    await expectSidebarBesideWorkspace(page);
    await expect(page.locator('textarea')).toBeVisible();
    await page.locator('textarea').click();

    await page.goto('/?lng=ar');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    await expectSidebarBesideWorkspace(page);
    await expect(page.locator('textarea')).toBeVisible();
    await page.locator('textarea').click();
  });
});
